"""Aster depth snapshot and stream capture helpers."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from typing import Any

import aiohttp

from ..config import AsterSourceConfig, AsterSymbolConfig
from ..contracts import build_market_event, build_recorder_error, build_rest_snapshot
from ..runtime import RecorderRuntime
from ..storage import RawJsonlZstWriter, RawStreamRoute, is_sealed_raw_file
from ..timeutil import utc_now_ns

_ASTER_DEPTH_WS_ERROR_ROUTE = RawStreamRoute(
	source="aster",
	transport="ws",
	source_symbol="MULTI",
	stream="recorder_error",
)
_ASTER_DEPTH_REST_ERROR_ROUTE = RawStreamRoute(
	source="aster",
	transport="rest",
	source_symbol="MULTI",
	stream="recorder_error",
)
_DEFAULT_RECONNECT_DELAY_SECONDS = 1.0


@dataclass(frozen=True, slots=True)
class AsterDepthStreamTarget:
	canonical_symbol: str
	source_symbol: str
	logical_stream: str
	stream_name: str
	stream_kind: str


@dataclass(frozen=True, slots=True)
class DiffDepthContinuityCheck:
	current_u: int | None
	observed_pu: int | None
	requires_restart: bool
	reason: str | None


@dataclass(frozen=True, slots=True)
class AsterDepthCaptureSummary:
	depth_record_count: int
	snapshot_record_count: int
	reconnect_count: int
	continuity_restart_count: int
	error_record_count: int
	output_paths: tuple[Path, ...]


def build_aster_depth_stream_targets(config: AsterSourceConfig) -> tuple[AsterDepthStreamTarget, ...]:
	targets: list[AsterDepthStreamTarget] = []
	for symbol in config.symbols:
		for logical_stream in config.streams:
			if not _is_depth_stream(logical_stream):
				continue
			targets.append(
				AsterDepthStreamTarget(
					canonical_symbol=symbol.canonical_symbol,
					source_symbol=symbol.source_symbol,
					logical_stream=logical_stream,
					stream_name=f"{symbol.source_symbol.lower()}@{logical_stream}",
					stream_kind=_classify_depth_stream(logical_stream),
				),
			)
	return tuple(targets)


def build_aster_depth_combined_stream_url(base_url: str, targets: tuple[AsterDepthStreamTarget, ...]) -> str:
	normalized_base = base_url.rstrip("/")
	stream_path = "/".join(target.stream_name for target in targets)
	return f"{normalized_base}/stream?streams={stream_path}"


def observe_diff_depth_continuity(
	*,
	previous_u: int | None,
	payload: dict[str, Any],
) -> DiffDepthContinuityCheck:
	data = payload.get("data")
	if not isinstance(data, dict):
		raise ValueError("Aster depth message missing data object")

	current_u = _read_depth_int(data, "u")
	if current_u is None:
		return DiffDepthContinuityCheck(
			current_u=None,
			observed_pu=None,
			requires_restart=True,
			reason="missing_u",
		)

	if previous_u is None:
		return DiffDepthContinuityCheck(
			current_u=current_u,
			observed_pu=_read_depth_int(data, "pu"),
			requires_restart=False,
			reason=None,
		)

	observed_pu = _read_depth_int(data, "pu")
	if observed_pu is None:
		return DiffDepthContinuityCheck(
			current_u=current_u,
			observed_pu=None,
			requires_restart=True,
			reason="missing_pu",
		)

	if observed_pu != previous_u:
		return DiffDepthContinuityCheck(
			current_u=current_u,
			observed_pu=observed_pu,
			requires_restart=True,
			reason="pu_mismatch",
		)

	return DiffDepthContinuityCheck(
		current_u=current_u,
		observed_pu=observed_pu,
		requires_restart=False,
		reason=None,
	)


async def capture_aster_depth(
	*,
	runtime: RecorderRuntime,
	event_limit: int | None = None,
	duration_seconds: float | None = None,
) -> AsterDepthCaptureSummary:
	config = runtime.config
	depth_config = config.sources.aster.depth
	targets = build_aster_depth_stream_targets(config.sources.aster)
	if not targets:
		return AsterDepthCaptureSummary(
			depth_record_count=0,
			snapshot_record_count=0,
			reconnect_count=0,
			continuity_restart_count=0,
			error_record_count=0,
			output_paths=(),
		)

	target_map = {target.stream_name: target for target in targets}
	combined_url = build_aster_depth_combined_stream_url(config.sources.aster.ws_base_url, targets)
	depth_writers = {
		target.stream_name: RawJsonlZstWriter(
			data_root=config.runtime.data_root,
			route=RawStreamRoute(
				source="aster",
				transport="ws",
				source_symbol=target.source_symbol,
				stream=target.logical_stream,
			),
			run_id=runtime.run_id,
			compression_level=config.storage.compression_level,
			rotation_policy=config.storage.resolve_rotation_policy(
				source="aster",
				stream=target.logical_stream,
			),
		)
		for target in targets
	}
	snapshot_writers = {
		symbol.source_symbol: RawJsonlZstWriter(
			data_root=config.runtime.data_root,
			route=RawStreamRoute(
				source="aster",
				transport="rest",
				source_symbol=symbol.source_symbol,
				stream=f"depth_snapshot_{depth_config.snapshot_limit}",
			),
			run_id=runtime.run_id,
			compression_level=config.storage.compression_level,
			rotation_policy=config.storage.resolve_rotation_policy(
				source="aster",
				stream=f"depth_snapshot_{depth_config.snapshot_limit}",
			),
		)
		for symbol in config.sources.aster.symbols
	}
	ws_error_writer = RawJsonlZstWriter(
		data_root=config.runtime.data_root,
		route=_ASTER_DEPTH_WS_ERROR_ROUTE,
		run_id=runtime.run_id,
		compression_level=config.storage.compression_level,
		rotation_policy=config.storage.resolve_rotation_policy(
			source=_ASTER_DEPTH_WS_ERROR_ROUTE.source,
			stream=_ASTER_DEPTH_WS_ERROR_ROUTE.stream,
		),
	)
	rest_error_writer = RawJsonlZstWriter(
		data_root=config.runtime.data_root,
		route=_ASTER_DEPTH_REST_ERROR_ROUTE,
		run_id=runtime.run_id,
		compression_level=config.storage.compression_level,
		rotation_policy=config.storage.resolve_rotation_policy(
			source=_ASTER_DEPTH_REST_ERROR_ROUTE.source,
			stream=_ASTER_DEPTH_REST_ERROR_ROUTE.stream,
		),
	)

	deadline = monotonic() + duration_seconds if duration_seconds is not None else None
	snapshot_due_at = {symbol.source_symbol: 0.0 for symbol in config.sources.aster.symbols}
	last_diff_u_by_stream = {
		target.stream_name: None
		for target in targets
		if target.stream_kind == "diff"
	}
	depth_record_count = 0
	snapshot_record_count = 0
	reconnect_count = 0
	continuity_restart_count = 0
	error_record_count = 0
	snapshot_request_count = 0
	connection_number = 0
	output_paths: set[Path] = set()

	try:
		while not _stop_requested(
			records_written=depth_record_count,
			event_limit=event_limit,
			deadline=deadline,
		):
			snapshot_record_count, snapshot_request_count, error_record_count = await _capture_due_snapshots(
				runtime=runtime,
				symbols=config.sources.aster.symbols,
				snapshot_writers=snapshot_writers,
				rest_error_writer=rest_error_writer,
				snapshot_due_at=snapshot_due_at,
				snapshot_record_count=snapshot_record_count,
				snapshot_request_count=snapshot_request_count,
				output_paths=output_paths,
				error_record_count=error_record_count,
			)
			connection_number += 1
			conn_id = f"{runtime.run_id}-aster-depth-{connection_number:03d}"
			try:
				async with runtime.session.ws_connect(
					combined_url,
					heartbeat=None,
					autoclose=True,
					autoping=True,
				) as ws:
					while not _stop_requested(
						records_written=depth_record_count,
						event_limit=event_limit,
						deadline=deadline,
					):
						snapshot_record_count, snapshot_request_count, error_record_count = await _capture_due_snapshots(
							runtime=runtime,
							symbols=config.sources.aster.symbols,
							snapshot_writers=snapshot_writers,
							rest_error_writer=rest_error_writer,
							snapshot_due_at=snapshot_due_at,
							snapshot_record_count=snapshot_record_count,
							snapshot_request_count=snapshot_request_count,
							output_paths=output_paths,
							error_record_count=error_record_count,
						)
						try:
							message = await ws.receive(timeout=1.0)
						except asyncio.TimeoutError:
							continue

						if message.type == aiohttp.WSMsgType.TEXT:
							payload = json.loads(message.data)
							if not isinstance(payload, dict):
								raise ValueError("Aster depth wrapper message was not a JSON object")
							stream_name = payload.get("stream")
							if not isinstance(stream_name, str):
								raise ValueError("Aster depth wrapper message missing stream name")
							target = target_map.get(stream_name)
							if target is None:
								raise ValueError(f"Unexpected Aster depth stream name: {stream_name}")

							depth_record_count += 1
							_add_output_path_if_sealed(
								output_paths,
								depth_writers[stream_name].write_record(
									build_market_event(
										source="aster",
										transport="ws",
										stream=target.logical_stream,
										stream_name=stream_name,
										canonical_symbol=target.canonical_symbol,
										source_symbol=target.source_symbol,
										conn_id=conn_id,
										seq=depth_record_count,
										payload=payload,
									),
								),
							)

							if target.stream_kind == "diff":
								expected_previous_u = last_diff_u_by_stream[stream_name]
								check = observe_diff_depth_continuity(
									previous_u=expected_previous_u,
									payload=payload,
								)
								last_diff_u_by_stream[stream_name] = check.current_u
								if check.requires_restart:
									continuity_restart_count += 1
									error_record_count += 1
									_add_output_path_if_sealed(
										output_paths,
										ws_error_writer.write_record(
											build_recorder_error(
												source="aster",
												transport="ws",
												stream="recorder_error",
												stream_name=stream_name,
												canonical_symbol=target.canonical_symbol,
												source_symbol=target.source_symbol,
												conn_id=conn_id,
												seq=error_record_count,
												payload={
													"kind": "depth_continuity_restart_required",
													"reason": check.reason,
													"expected_previous_u": expected_previous_u,
													"observed_pu": check.observed_pu,
													"observed_u": check.current_u,
												},
											),
										),
									)
									ws_error_writer.flush()

						elif message.type in {aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSE}:
							break
						elif message.type == aiohttp.WSMsgType.ERROR:
							raise aiohttp.ClientError(str(ws.exception()))

					_flush_all_writers(depth_writers, snapshot_writers, ws_error_writer, rest_error_writer)
					if _stop_requested(
						records_written=depth_record_count,
						event_limit=event_limit,
						deadline=deadline,
					):
						break
					reconnect_count += 1
					await asyncio.sleep(_DEFAULT_RECONNECT_DELAY_SECONDS)
			except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, json.JSONDecodeError) as exc:
				reconnect_count += 1
				error_record_count += 1
				_add_output_path_if_sealed(
					output_paths,
					ws_error_writer.write_record(
						build_recorder_error(
							source="aster",
							transport="ws",
							stream="recorder_error",
							stream_name=None,
							canonical_symbol="MULTI",
							source_symbol="MULTI",
							conn_id=conn_id,
							seq=error_record_count,
							payload={
								"kind": exc.__class__.__name__,
								"message": str(exc),
								"url": combined_url,
							},
						),
					),
				)
				ws_error_writer.flush()
				if _stop_requested(
					records_written=depth_record_count,
					event_limit=event_limit,
					deadline=deadline,
				):
					break
				await asyncio.sleep(_DEFAULT_RECONNECT_DELAY_SECONDS)
	finally:
		_close_all_writers(depth_writers, snapshot_writers, ws_error_writer, rest_error_writer)
		output_paths.update(
			_collect_sealed_output_paths(
				*depth_writers.values(),
				*snapshot_writers.values(),
				ws_error_writer,
				rest_error_writer,
			),
		)

	return AsterDepthCaptureSummary(
		depth_record_count=depth_record_count,
		snapshot_record_count=snapshot_record_count,
		reconnect_count=reconnect_count,
		continuity_restart_count=continuity_restart_count,
		error_record_count=error_record_count,
		output_paths=tuple(sorted(output_paths)),
	)


async def _capture_due_snapshots(
	*,
	runtime: RecorderRuntime,
	symbols: tuple[AsterSymbolConfig, ...],
	snapshot_writers: dict[str, RawJsonlZstWriter],
	rest_error_writer: RawJsonlZstWriter,
	snapshot_due_at: dict[str, float],
	snapshot_record_count: int,
	snapshot_request_count: int,
	output_paths: set[Path],
	error_record_count: int,
) -> tuple[int, int, int]:
	interval_seconds = runtime.config.sources.aster.depth.snapshot_interval_seconds
	for symbol in symbols:
		now = monotonic()
		if now < snapshot_due_at[symbol.source_symbol]:
			continue
		try:
			snapshot_request_count += 1
			_add_output_path_if_sealed(
				output_paths,
				await _write_depth_snapshot(
					runtime=runtime,
					symbol=symbol,
					snapshot_writer=snapshot_writers[symbol.source_symbol],
					seq=snapshot_record_count + 1,
					request_index=snapshot_request_count,
				),
			)
			snapshot_record_count += 1
			snapshot_due_at[symbol.source_symbol] = monotonic() + interval_seconds
			rest_error_writer.flush()
		except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, json.JSONDecodeError) as exc:
			error_record_count += 1
			_add_output_path_if_sealed(
				output_paths,
				rest_error_writer.write_record(
					build_recorder_error(
						source="aster",
						transport="rest",
						stream="recorder_error",
						stream_name=None,
						canonical_symbol=symbol.canonical_symbol,
						source_symbol=symbol.source_symbol,
						conn_id=f"{runtime.run_id}-aster-rest-{snapshot_request_count:03d}",
						seq=error_record_count,
						payload={
							"kind": exc.__class__.__name__,
							"message": str(exc),
							"url": f"{runtime.config.sources.aster.rest_base_url.rstrip('/')}/fapi/v1/depth",
							"params": {
								"symbol": symbol.source_symbol,
								"limit": runtime.config.sources.aster.depth.snapshot_limit,
							},
						},
					),
				),
			)
			rest_error_writer.flush()
	return snapshot_record_count, snapshot_request_count, error_record_count


async def _write_depth_snapshot(
	*,
	runtime: RecorderRuntime,
	symbol: AsterSymbolConfig,
	snapshot_writer: RawJsonlZstWriter,
	seq: int,
	request_index: int,
) -> Path:
	config = runtime.config.sources.aster
	request_ts_ns = utc_now_ns()
	url = f"{config.rest_base_url.rstrip('/')}/fapi/v1/depth"
	params = {"symbol": symbol.source_symbol, "limit": config.depth.snapshot_limit}
	async with runtime.session.get(
		url,
		params=params,
		timeout=aiohttp.ClientTimeout(total=10, connect=5, sock_read=10),
	) as response:
		response.raise_for_status()
		payload = await response.json()

	return snapshot_writer.write_record(
		build_rest_snapshot(
			source="aster",
			transport="rest",
			stream=f"depth_snapshot_{config.depth.snapshot_limit}",
			stream_name=None,
			canonical_symbol=symbol.canonical_symbol,
			source_symbol=symbol.source_symbol,
			conn_id=f"{runtime.run_id}-aster-rest-{request_index:03d}",
			seq=seq,
			payload={
				"status": response.status,
				"request_ts_ns": request_ts_ns,
				"url": url,
				"params": params,
				"rate_limit_headers": _extract_rate_limit_headers(response.headers),
				"data": payload,
			},
		),
	)


def _classify_depth_stream(logical_stream: str) -> str:
	stream_name = logical_stream.lower()
	if stream_name.startswith("depth@"):
		return "diff"
	return "partial"


def _extract_rate_limit_headers(headers: aiohttp.typedefs.LooseHeaders) -> dict[str, str]:
	if not hasattr(headers, "items"):
		return {}
	return {
		key: value
		for key, value in headers.items()
		if key.upper().startswith("X-MBX-USED-WEIGHT")
	}


def _is_depth_stream(logical_stream: str) -> bool:
	stream_name = logical_stream.lower()
	return stream_name.startswith("depth") or "depth" in stream_name


def _read_depth_int(mapping: dict[str, Any], key: str) -> int | None:
	value = mapping.get(key)
	if isinstance(value, bool):
		return None
	if isinstance(value, int):
		return value
	if isinstance(value, str):
		try:
			return int(value)
		except ValueError:
			return None
	return None


def _flush_all_writers(
	depth_writers: dict[str, RawJsonlZstWriter],
	snapshot_writers: dict[str, RawJsonlZstWriter],
	ws_error_writer: RawJsonlZstWriter,
	rest_error_writer: RawJsonlZstWriter,
) -> None:
	for writer in depth_writers.values():
		writer.flush()
	for writer in snapshot_writers.values():
		writer.flush()
	ws_error_writer.flush()
	rest_error_writer.flush()


def _close_all_writers(
	depth_writers: dict[str, RawJsonlZstWriter],
	snapshot_writers: dict[str, RawJsonlZstWriter],
	ws_error_writer: RawJsonlZstWriter,
	rest_error_writer: RawJsonlZstWriter,
) -> None:
	for writer in depth_writers.values():
		writer.close()
	for writer in snapshot_writers.values():
		writer.close()
	ws_error_writer.close()
	rest_error_writer.close()


def _stop_requested(*, records_written: int, event_limit: int | None, deadline: float | None) -> bool:
	if event_limit is not None and records_written >= event_limit:
		return True
	if deadline is not None and monotonic() >= deadline:
		return True
	return False


def _add_output_path_if_sealed(output_paths: set[Path], path: Path) -> None:
	if is_sealed_raw_file(path):
		output_paths.add(path)


def _collect_sealed_output_paths(*writers: RawJsonlZstWriter) -> set[Path]:
	sealed_paths: set[Path] = set()
	for writer in writers:
		for segment in writer.sealed_segments:
			sealed_paths.add(segment.sealed_path)
	return sealed_paths