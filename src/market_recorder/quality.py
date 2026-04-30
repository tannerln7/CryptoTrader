"""Route-aware raw data quality reporting."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .config import RecorderConfig
from .sources import build_aster_stream_targets
from .sources.aster_depth import build_aster_depth_stream_targets
from .storage import is_active_raw_file, sanitize_path_component, validate_raw_file


@dataclass(frozen=True, slots=True)
class RouteQualitySummary:
	route: str
	status: str
	latest_path: str | None
	latest_output_utc: str | None
	record_count: int | None
	message: str | None
	required: bool


@dataclass(frozen=True, slots=True)
class ExpectedRoute:
	route: str
	required: bool
	note: str | None = None


@dataclass(frozen=True, slots=True)
class DataQualityReport:
	checked_route_count: int
	ok_route_count: int
	missing_route_count: int
	stale_route_count: int
	invalid_route_count: int
	routes: tuple[RouteQualitySummary, ...]


def build_data_quality_report(
	config: RecorderConfig,
	*,
	stale_after_seconds: float,
) -> DataQualityReport:
	expected_routes = _expected_routes(config)
	actual_routes = _group_raw_files(config.runtime.data_root)
	active_routes = _group_active_raw_files(config.runtime.data_root)
	routes: list[RouteQualitySummary] = []
	ok_route_count = 0
	missing_route_count = 0
	stale_route_count = 0
	invalid_route_count = 0

	for route, expected in sorted(expected_routes.items()):
		paths = actual_routes.get(route)
		active_paths = active_routes.get(route, [])
		if not paths:
			if active_paths:
				latest_active_path = max(active_paths, key=lambda candidate: candidate.stat().st_mtime)
				latest_active_output = datetime.fromtimestamp(latest_active_path.stat().st_mtime, tz=UTC)
				latest_active_output_utc = latest_active_output.isoformat().replace("+00:00", "Z")
				active_age_seconds = max((datetime.now(UTC) - latest_active_output).total_seconds(), 0.0)
				status = "incomplete-active"
				message = "Found active raw segment(s); sealed validation skipped"
				if active_age_seconds > stale_after_seconds:
					status = "stale-active"
					message = f"Latest active raw segment is {active_age_seconds:.1f}s old; sealed validation skipped"
				routes.append(
					RouteQualitySummary(
						route=route,
						status=status,
						latest_path=str(latest_active_path),
						latest_output_utc=latest_active_output_utc,
						record_count=None,
						message=message,
						required=expected.required,
					),
				)
				continue
			status = "missing"
			message = "No raw files found for expected route"
			if not expected.required:
				status = "optional-missing"
				message = expected.note or "Route is event-driven and may legitimately have no files yet"
			else:
				missing_route_count += 1
			routes.append(
				RouteQualitySummary(
					route=route,
					status=status,
					latest_path=None,
					latest_output_utc=None,
					record_count=None,
					message=message,
					required=expected.required,
				),
			)
			continue

		latest_path = max(paths, key=lambda candidate: candidate.stat().st_mtime)
		latest_output = datetime.fromtimestamp(latest_path.stat().st_mtime, tz=UTC)
		latest_output_utc = latest_output.isoformat().replace("+00:00", "Z")
		age_seconds = max((datetime.now(UTC) - latest_output).total_seconds(), 0.0)

		try:
			validation = validate_raw_file(latest_path)
		except ValueError as exc:
			invalid_route_count += 1
			routes.append(
				RouteQualitySummary(
					route=route,
					status="invalid",
					latest_path=str(latest_path),
					latest_output_utc=latest_output_utc,
					record_count=None,
					message=str(exc),
					required=expected.required,
				),
			)
			continue

		if age_seconds > stale_after_seconds:
			stale_route_count += 1
			status = "stale"
			message = f"Latest raw file is {age_seconds:.1f}s old"
		else:
			ok_route_count += 1
			status = "ok"
			message = None

		if active_paths:
			active_note = f"{len(active_paths)} active segment(s) skipped"
			message = active_note if message is None else f"{message}; {active_note}"

		routes.append(
			RouteQualitySummary(
				route=route,
				status=status,
				latest_path=str(latest_path),
				latest_output_utc=latest_output_utc,
				record_count=validation.record_count,
				message=message,
				required=expected.required,
			),
		)

	return DataQualityReport(
		checked_route_count=len(expected_routes),
		ok_route_count=ok_route_count,
		missing_route_count=missing_route_count,
		stale_route_count=stale_route_count,
		invalid_route_count=invalid_route_count,
		routes=tuple(routes),
	)


def _expected_routes(config: RecorderConfig) -> dict[str, ExpectedRoute]:
	routes: dict[str, ExpectedRoute] = {}
	if config.sources.pyth.enabled:
		routes["pyth/sse/MULTI/price_stream"] = ExpectedRoute(
			route="pyth/sse/MULTI/price_stream",
			required=True,
		)
	if config.sources.aster.enabled:
		for target in build_aster_stream_targets(config.sources.aster):
			route = _sanitized_route("aster", "ws", target.source_symbol, target.logical_stream)
			routes[route] = ExpectedRoute(
				route=route,
				required=target.logical_stream != "forceOrder",
				note="forceOrder is activity-driven and may be absent during quiet windows",
			)
		for target in build_aster_depth_stream_targets(config.sources.aster):
			route = _sanitized_route("aster", "ws", target.source_symbol, target.logical_stream)
			routes[route] = ExpectedRoute(route=route, required=True)
		for symbol in config.sources.aster.symbols:
			route = _sanitized_route(
				"aster",
				"rest",
				symbol.source_symbol,
				f"depth_snapshot_{config.sources.aster.depth.snapshot_limit}",
			)
			routes[route] = ExpectedRoute(
				route=route,
				required=True,
			)
	if config.sources.tradingview.enabled:
		routes["tradingview/webhook/ALL/alert"] = ExpectedRoute(
			route="tradingview/webhook/ALL/alert",
			required=False,
			note="TradingView alerts are event-driven and may be absent until an alert fires",
		)
	return routes


def _sanitized_route(source: str, transport: str, source_symbol: str, stream: str) -> str:
	return "/".join(
		[
			sanitize_path_component(source),
			sanitize_path_component(transport),
			sanitize_path_component(source_symbol),
			sanitize_path_component(stream),
		],
	)


def _group_raw_files(data_root: Path) -> dict[str, list[Path]]:
	routes: dict[str, list[Path]] = {}
	raw_root = data_root / "raw"
	if not raw_root.exists():
		return routes
	for path in raw_root.rglob("part-*.jsonl.zst"):
		relative = path.relative_to(raw_root)
		parts = relative.parts
		if len(parts) < 4:
			continue
		route = "/".join(parts[:4])
		routes.setdefault(route, []).append(path)
	return routes


def _group_active_raw_files(data_root: Path) -> dict[str, list[Path]]:
	routes: dict[str, list[Path]] = {}
	raw_root = data_root / "raw"
	if not raw_root.exists():
		return routes
	for path in raw_root.rglob("part-*.jsonl.zst.open"):
		if not is_active_raw_file(path):
			continue
		relative = path.relative_to(raw_root)
		parts = relative.parts
		if len(parts) < 4:
			continue
		route = "/".join(parts[:4])
		routes.setdefault(route, []).append(path)
	return routes