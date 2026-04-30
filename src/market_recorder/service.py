"""Unattended recorder service orchestration and runtime health manifests."""

from __future__ import annotations

import asyncio
import contextlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from collections.abc import Awaitable, Callable
from typing import Any

from .alerts import TradingViewWebhookService
from .runtime import RecorderRuntime
from .sources import build_aster_stream_targets, capture_aster, capture_pyth
from .sources.aster_depth import build_aster_depth_stream_targets, capture_aster_depth
from .timeutil import utc_now_iso


@dataclass(frozen=True, slots=True)
class ComponentOutputObservation:
	file_count: int
	latest_output_path: str | None
	latest_output_utc: str | None


@dataclass(frozen=True, slots=True)
class RecorderServiceSummary:
	run_id: str
	started_at_utc: str
	finished_at_utc: str
	health_path: Path
	component_statuses: dict[str, str]
	component_outputs: dict[str, ComponentOutputObservation]


async def run_recorder_service(
	*,
	runtime: RecorderRuntime,
	duration_seconds: float | None = None,
	health_interval_seconds: float = 10.0,
	health_path: Path | None = None,
	on_ready: Callable[[], Awaitable[None] | None] | None = None,
) -> RecorderServiceSummary:
	component_names = _enabled_component_names(runtime)
	if not component_names:
		raise ValueError("No enabled recorder components are configured")

	started_at_utc = utc_now_iso()
	resolved_health_path = health_path or default_health_manifest_path(runtime.config.runtime.data_root, runtime.run_id)
	tradingview_service: TradingViewWebhookService | None = None
	component_tasks: dict[str, asyncio.Task[Any]] = {}
	health_task: asyncio.Task[None] | None = None
	component_statuses = {name: "pending" for name in component_names}

	try:
		if runtime.config.sources.tradingview.enabled:
			tradingview_service = TradingViewWebhookService.from_runtime(runtime)
			await tradingview_service.start()
		else:
			await runtime.start()

		health_task = _create_tracked_task(
			runtime,
			"service.health",
			_health_reporter_loop(
				runtime=runtime,
				component_tasks=component_tasks,
				started_at_utc=started_at_utc,
				health_path=resolved_health_path,
				interval_seconds=health_interval_seconds,
			),
		)

		if runtime.config.sources.pyth.enabled:
			component_tasks["pyth"] = _create_tracked_task(
				runtime,
				"pyth",
				capture_pyth(runtime=runtime, duration_seconds=duration_seconds),
			)
		if runtime.config.sources.aster.enabled and build_aster_stream_targets(runtime.config.sources.aster):
			component_tasks["aster.market"] = _create_tracked_task(
				runtime,
				"aster.market",
				capture_aster(runtime=runtime, duration_seconds=duration_seconds),
			)
		if runtime.config.sources.aster.enabled and build_aster_depth_stream_targets(runtime.config.sources.aster):
			component_tasks["aster.depth"] = _create_tracked_task(
				runtime,
				"aster.depth",
				capture_aster_depth(runtime=runtime, duration_seconds=duration_seconds),
			)
		if tradingview_service is not None:
			component_tasks["tradingview.webhook"] = _create_tracked_task(
				runtime,
				"tradingview.webhook",
				_run_started_tradingview_service(tradingview_service, duration_seconds=duration_seconds),
			)

		await write_runtime_health_snapshot(
			runtime=runtime,
			component_tasks=component_tasks,
			started_at_utc=started_at_utc,
			health_path=resolved_health_path,
		)
		await _invoke_on_ready(on_ready)

		await asyncio.gather(*(component_tasks[name] for name in component_tasks))
		for name in component_tasks:
			component_statuses[name] = "completed"
		component_outputs = collect_run_output_observations(runtime.config.runtime.data_root, runtime.run_id)
		await write_runtime_health_snapshot(
			runtime=runtime,
			component_tasks=component_tasks,
			started_at_utc=started_at_utc,
			health_path=resolved_health_path,
			component_statuses=component_statuses,
		)
		return RecorderServiceSummary(
			run_id=runtime.run_id,
			started_at_utc=started_at_utc,
			finished_at_utc=utc_now_iso(),
			health_path=resolved_health_path,
			component_statuses=component_statuses,
			component_outputs=component_outputs,
		)
	except asyncio.CancelledError:
		for name, task in component_tasks.items():
			if not task.done():
				component_statuses[name] = "cancelled"
				task.cancel()
		await asyncio.gather(*component_tasks.values(), return_exceptions=True)
		await write_runtime_health_snapshot(
			runtime=runtime,
			component_tasks=component_tasks,
			started_at_utc=started_at_utc,
			health_path=resolved_health_path,
			component_statuses=component_statuses,
		)
		raise
	except Exception:
		for name, task in component_tasks.items():
			if task.done() and task.exception() is not None:
				component_statuses[name] = "failed"
			elif not task.done():
				component_statuses[name] = "cancelled"
				task.cancel()
		await asyncio.gather(*component_tasks.values(), return_exceptions=True)
		await write_runtime_health_snapshot(
			runtime=runtime,
			component_tasks=component_tasks,
			started_at_utc=started_at_utc,
			health_path=resolved_health_path,
			component_statuses=component_statuses,
		)
		raise
	finally:
		if health_task is not None:
			health_task.cancel()
			with contextlib.suppress(asyncio.CancelledError):
				await health_task
		if tradingview_service is not None:
			await tradingview_service.close()


def default_health_manifest_path(data_root: Path, run_id: str) -> Path:
	return data_root / "manifests" / "runtime" / f"health-{run_id}.json"


def collect_run_output_observations(data_root: Path, run_id: str) -> dict[str, ComponentOutputObservation]:
	observations: dict[str, list[Path]] = {}
	raw_root = data_root / "raw"
	if raw_root.exists():
		for path in raw_root.rglob(f"part-{run_id}.jsonl.zst"):
			component_name = _component_name_for_output_path(path, data_root)
			observations.setdefault(component_name, []).append(path)

	component_observations: dict[str, ComponentOutputObservation] = {}
	for component_name, paths in observations.items():
		latest_path = max(paths, key=lambda candidate: candidate.stat().st_mtime)
		latest_time = datetime.fromtimestamp(latest_path.stat().st_mtime, tz=UTC)
		component_observations[component_name] = ComponentOutputObservation(
			file_count=len(paths),
			latest_output_path=str(latest_path),
			latest_output_utc=latest_time.isoformat().replace("+00:00", "Z"),
		)
	return component_observations


async def write_runtime_health_snapshot(
	*,
	runtime: RecorderRuntime,
	component_tasks: dict[str, asyncio.Task[Any]],
	started_at_utc: str,
	health_path: Path,
	component_statuses: dict[str, str] | None = None,
) -> None:
	observations = collect_run_output_observations(runtime.config.runtime.data_root, runtime.run_id)
	payload = {
		"run_id": runtime.run_id,
		"started_at_utc": started_at_utc,
		"updated_at_utc": utc_now_iso(),
		"enabled_components": _enabled_component_names(runtime),
		"component_statuses": component_statuses or {
			name: _task_state(task)
			for name, task in component_tasks.items()
		},
		"component_outputs": {
			name: asdict(observation)
			for name, observation in observations.items()
		},
	}
	health_path.parent.mkdir(parents=True, exist_ok=True)
	health_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


async def _health_reporter_loop(
	*,
	runtime: RecorderRuntime,
	component_tasks: dict[str, asyncio.Task[Any]],
	started_at_utc: str,
	health_path: Path,
	interval_seconds: float,
) -> None:
	while True:
		await write_runtime_health_snapshot(
			runtime=runtime,
			component_tasks=component_tasks,
			started_at_utc=started_at_utc,
			health_path=health_path,
		)
		await asyncio.sleep(interval_seconds)


async def _run_started_tradingview_service(
	service: TradingViewWebhookService,
	*,
	duration_seconds: float | None,
) -> Any:
	await service.wait(duration_seconds=duration_seconds)
	return service.build_summary()


async def _invoke_on_ready(
	on_ready: Callable[[], Awaitable[None] | None] | None,
) -> None:
	if on_ready is None:
		return
	result = on_ready()
	if result is not None:
		await result


def _create_tracked_task(
	runtime: RecorderRuntime,
	name: str,
	coro: Any,
) -> asyncio.Task[Any]:
	task = asyncio.create_task(coro, name=name)
	runtime.background_tasks.add(task)
	task.add_done_callback(runtime.background_tasks.discard)
	return task


def _enabled_component_names(runtime: RecorderRuntime) -> tuple[str, ...]:
	components: list[str] = []
	if runtime.config.sources.pyth.enabled:
		components.append("pyth")
	if runtime.config.sources.aster.enabled and build_aster_stream_targets(runtime.config.sources.aster):
		components.append("aster.market")
	if runtime.config.sources.aster.enabled and build_aster_depth_stream_targets(runtime.config.sources.aster):
		components.append("aster.depth")
	if runtime.config.sources.tradingview.enabled:
		components.append("tradingview.webhook")
	return tuple(components)


def _component_name_for_output_path(path: Path, data_root: Path) -> str:
	relative = path.relative_to(data_root / "raw")
	parts = relative.parts
	if len(parts) < 4:
		return "unknown"
	source, transport, _source_symbol, stream = parts[:4]
	if source == "pyth":
		return "pyth"
	if source == "tradingview":
		return "tradingview.webhook"
	if source == "aster":
		if transport == "rest" and stream.startswith("depth_snapshot_"):
			return "aster.depth"
		if transport == "ws" and "depth" in stream:
			return "aster.depth"
		return "aster.market"
	return source


def _task_state(task: asyncio.Task[Any]) -> str:
	if task.cancelled():
		return "cancelled"
	if not task.done():
		return "running"
	if task.exception() is not None:
		return "failed"
	return "completed"