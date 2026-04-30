"""TradingView webhook alert capture helpers."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aiohttp import web

from ..contracts import build_alert_event, build_recorder_error
from ..runtime import RecorderRuntime
from ..storage import RawJsonlZstWriter, RawStreamRoute, is_sealed_raw_file

_TRADINGVIEW_ALERT_ROUTE = RawStreamRoute(
	source="tradingview",
	transport="webhook",
	source_symbol="ALL",
	stream="alert",
)
_TRADINGVIEW_ERROR_ROUTE = RawStreamRoute(
	source="tradingview",
	transport="webhook",
	source_symbol="ALL",
	stream="recorder_error",
)


@dataclass(frozen=True, slots=True)
class TradingViewWebhookSummary:
	request_count: int
	error_record_count: int
	bind_host: str
	bind_port: int
	path: str
	output_paths: tuple[Path, ...]


@dataclass(slots=True)
class TradingViewWebhookService:
	runtime: RecorderRuntime
	bind_host: str
	bind_port: int
	path: str
	request_limit: int | None = None
	_writer: RawJsonlZstWriter | None = None
	_error_writer: RawJsonlZstWriter | None = None
	_site: web.TCPSite | None = None
	_done: asyncio.Event = field(default_factory=asyncio.Event)
	_started: bool = False
	request_count: int = 0
	error_record_count: int = 0
	output_paths: set[Path] = field(default_factory=set)
	actual_port: int | None = None

	@classmethod
	def from_runtime(
		cls,
		runtime: RecorderRuntime,
		*,
		bind_host: str | None = None,
		bind_port: int | None = None,
		path: str | None = None,
		request_limit: int | None = None,
	) -> "TradingViewWebhookService":
		config = runtime.config.sources.tradingview.webhook
		return cls(
			runtime=runtime,
			bind_host=bind_host or config.bind_host,
			bind_port=config.bind_port if bind_port is None else bind_port,
			path=path or config.path,
			request_limit=request_limit,
		)

	@property
	def base_url(self) -> str:
		port = self.actual_port if self.actual_port is not None else self.bind_port
		return f"http://{self.bind_host}:{port}"

	async def start(self) -> None:
		if self._started:
			return
		self._writer = RawJsonlZstWriter(
			data_root=self.runtime.config.runtime.data_root,
			route=_TRADINGVIEW_ALERT_ROUTE,
			run_id=self.runtime.run_id,
			compression_level=self.runtime.config.storage.compression_level,
			rotation_policy=self.runtime.config.storage.resolve_rotation_policy(
				source=_TRADINGVIEW_ALERT_ROUTE.source,
				stream=_TRADINGVIEW_ALERT_ROUTE.stream,
			),
		)
		self._error_writer = RawJsonlZstWriter(
			data_root=self.runtime.config.runtime.data_root,
			route=_TRADINGVIEW_ERROR_ROUTE,
			run_id=self.runtime.run_id,
			compression_level=self.runtime.config.storage.compression_level,
			rotation_policy=self.runtime.config.storage.resolve_rotation_policy(
				source=_TRADINGVIEW_ERROR_ROUTE.source,
				stream=_TRADINGVIEW_ERROR_ROUTE.stream,
			),
		)
		self.runtime.app.router.add_post(self.path, self.handle_request)
		self._site = await self.runtime.start_site(self.bind_host, self.bind_port)
		sockets = getattr(getattr(self._site, "_server", None), "sockets", None)
		if sockets:
			self.actual_port = sockets[0].getsockname()[1]
		else:
			self.actual_port = self.bind_port
		self._started = True

	async def wait(self, *, duration_seconds: float | None = None) -> None:
		if duration_seconds is None and self.request_limit is None:
			await asyncio.Future()
			return
		if duration_seconds is None:
			await self._done.wait()
			return
		try:
			await asyncio.wait_for(self._done.wait(), timeout=duration_seconds)
		except asyncio.TimeoutError:
			return

	async def close(self) -> None:
		if self._writer is not None:
			self._writer.close()
			self.output_paths.update(_collect_sealed_output_paths(self._writer))
			self._writer = None
		if self._error_writer is not None:
			self._error_writer.close()
			self.output_paths.update(_collect_sealed_output_paths(self._error_writer))
			self._error_writer = None
		self._started = False

	def build_summary(self) -> TradingViewWebhookSummary:
		port = self.actual_port if self.actual_port is not None else self.bind_port
		return TradingViewWebhookSummary(
			request_count=self.request_count,
			error_record_count=self.error_record_count,
			bind_host=self.bind_host,
			bind_port=port,
			path=self.path,
			output_paths=tuple(sorted(self.output_paths)),
		)

	async def handle_request(self, request: web.Request) -> web.Response:
		if self._writer is None or self._error_writer is None:
			raise RuntimeError("TradingView webhook service has not been started")

		body_text = await request.text()
		try:
			body, body_format = parse_tradingview_body(request.content_type, body_text)
		except ValueError as exc:
			self.error_record_count += 1
			_add_output_path_if_sealed(
				self.output_paths,
				self._error_writer.write_record(
					build_recorder_error(
						source="tradingview",
						transport="webhook",
						stream="recorder_error",
						stream_name=request.path,
						canonical_symbol="ALL",
						source_symbol="ALL",
						conn_id=f"{self.runtime.run_id}-tradingview-webhook",
						seq=self.error_record_count,
						payload={
							"kind": "invalid_json",
							"message": str(exc),
							"content_type": request.content_type,
							"path": request.path,
							"body": body_text,
						},
					),
				),
			)
			self._error_writer.flush()
			return web.Response(status=400, text="invalid json")

		self.request_count += 1
		_add_output_path_if_sealed(
			self.output_paths,
			self._writer.write_record(
				build_alert_event(
					source="tradingview",
					transport="webhook",
					stream="alert",
					stream_name=request.path,
					canonical_symbol="ALL",
					source_symbol="ALL",
					conn_id=f"{self.runtime.run_id}-tradingview-webhook",
					seq=self.request_count,
					payload={
						"content_type": request.content_type,
						"body_format": body_format,
						"body": body,
						"path": request.path,
						"query": dict(request.query),
						"headers": _extract_request_headers(request),
					},
				),
			),
		)
		self._writer.flush()

		if self.request_limit is not None and self.request_count >= self.request_limit:
			self._done.set()

		return web.Response(status=200, text="ok")


def parse_tradingview_body(content_type: str, body_text: str) -> tuple[Any, str]:
	if content_type == "application/json":
		try:
			return json.loads(body_text), "json"
		except json.JSONDecodeError as exc:
			raise ValueError("TradingView body declared application/json but did not parse") from exc
	return body_text, "text"


async def serve_tradingview_webhook(
	*,
	runtime: RecorderRuntime,
	duration_seconds: float | None = None,
	request_limit: int | None = None,
	bind_host: str | None = None,
	bind_port: int | None = None,
	path: str | None = None,
) -> TradingViewWebhookSummary:
	service = TradingViewWebhookService.from_runtime(
		runtime,
		bind_host=bind_host,
		bind_port=bind_port,
		path=path,
		request_limit=request_limit,
	)
	await service.start()
	try:
		await service.wait(duration_seconds=duration_seconds)
	finally:
		await service.close()
	return service.build_summary()


def _add_output_path_if_sealed(output_paths: set[Path], path: Path) -> None:
	if is_sealed_raw_file(path):
		output_paths.add(path)


def _collect_sealed_output_paths(*writers: RawJsonlZstWriter) -> set[Path]:
	sealed_paths: set[Path] = set()
	for writer in writers:
		for segment in writer.sealed_segments:
			sealed_paths.add(segment.sealed_path)
	return sealed_paths


def _extract_request_headers(request: web.Request) -> dict[str, str]:
	interesting_headers = ("Content-Type", "User-Agent", "X-Forwarded-For")
	return {
		header: value
		for header in interesting_headers
		if (value := request.headers.get(header)) is not None
	}