"""CLI entrypoints for recorder validation, capture, and service operations."""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from . import __version__
from .alerts import TradingViewWebhookSummary, serve_tradingview_webhook
from .config import (
    DEFAULT_CONFIG_PATH,
    REPO_ROOT,
    ConfigError,
    apply_runtime_overrides,
    load_config,
)
from .contracts import build_market_event
from .logging import configure_logging, get_logger
from .quality import DataQualityReport, build_data_quality_report
from .runtime import RecorderRuntime
from .service import RecorderServiceSummary, run_recorder_service
from .service_control import (
    RecorderServiceLaunchSpec,
    RecorderServiceStatus,
    ServiceControlError,
    build_service_launch_spec,
    load_service_health,
    read_service_status,
    run_service_worker_foreground,
    start_background_service,
    stop_background_service,
)
from .sources.aster import AsterCaptureSummary, capture_aster
from .sources.aster_depth import AsterDepthCaptureSummary, capture_aster_depth
from .sources.pyth import PythCaptureSummary, capture_pyth
from .storage import (
    RawFileValidationSummary,
    RawJsonlZstWriter,
    RawStreamRoute,
    validate_raw_file,
)
from .timeutil import make_run_id


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="market-recorder",
        description="Control and inspect the market recorder service.",
        allow_abbrev=False,
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Print the recorder package version and exit.",
    )
    _add_config_arguments(parser)

    subparsers = parser.add_subparsers(dest="command")
    start_parser = subparsers.add_parser(
        "start",
        help="Start the recorder service in the background.",
    )
    _add_config_arguments(start_parser, suppress_defaults=True)
    _add_service_control_arguments(start_parser)

    stop_parser = subparsers.add_parser(
        "stop",
        help="Stop the running recorder service.",
    )
    _add_config_arguments(stop_parser, suppress_defaults=True)

    restart_parser = subparsers.add_parser(
        "restart",
        help="Restart the recorder service.",
    )
    _add_config_arguments(restart_parser, suppress_defaults=True)
    _add_service_control_arguments(restart_parser)

    status_parser = subparsers.add_parser(
        "status",
        help="Show recorder service status.",
    )
    _add_config_arguments(status_parser, suppress_defaults=True)

    health_parser = subparsers.add_parser(
        "health",
        help="Show summarized recorder service health.",
    )
    _add_config_arguments(health_parser, suppress_defaults=True)

    validate_config_parser = subparsers.add_parser(
        "validate-config",
        help="Load and validate the runtime and sources config.",
    )
    _add_config_arguments(validate_config_parser, suppress_defaults=True)

    write_sample_parser = subparsers.add_parser(
        "write-sample",
        help="Development/debug: write a sample raw .jsonl.zst file.",
    )
    _add_config_arguments(write_sample_parser, suppress_defaults=True)
    write_sample_parser.add_argument("--source", default="sample", help="Logical source name for the sample route.")
    write_sample_parser.add_argument(
        "--transport",
        default="internal",
        help="Transport name for the sample route.",
    )
    write_sample_parser.add_argument(
        "--source-symbol",
        default="SAMPLE",
        help="Source symbol for the sample route.",
    )
    write_sample_parser.add_argument(
        "--stream",
        default="sample_stream",
        help="Logical stream name for the sample route.",
    )

    run_parser = subparsers.add_parser(
        "run",
        help="Development/debug: initialize the runtime and exit after startup checks.",
    )
    _add_config_arguments(run_parser, suppress_defaults=True)

    run_service_parser = subparsers.add_parser(
        "run-service",
        help="Development/debug: run the recorder worker in the foreground.",
    )
    _add_config_arguments(run_service_parser, suppress_defaults=True)
    _add_service_control_arguments(run_service_parser, health_interval_default=10.0)

    capture_pyth_parser = subparsers.add_parser(
        "capture-pyth",
        help="Development/debug: capture live Pyth SSE updates into raw storage.",
    )
    _add_config_arguments(capture_pyth_parser, suppress_defaults=True)
    capture_pyth_parser.add_argument(
        "--event-limit",
        type=int,
        default=None,
        help="Optional maximum number of Pyth events to capture before exiting.",
    )
    capture_pyth_parser.add_argument(
        "--duration-seconds",
        type=float,
        default=None,
        help="Optional maximum runtime for the Pyth capture command.",
    )

    capture_aster_parser = subparsers.add_parser(
        "capture-aster",
        help="Development/debug: capture live Aster non-depth market streams into raw storage.",
    )
    _add_config_arguments(capture_aster_parser, suppress_defaults=True)
    capture_aster_parser.add_argument(
        "--event-limit",
        type=int,
        default=None,
        help="Optional maximum number of Aster events to capture before exiting.",
    )
    capture_aster_parser.add_argument(
        "--duration-seconds",
        type=float,
        default=None,
        help="Optional maximum runtime for the Aster capture command.",
    )

    capture_aster_depth_parser = subparsers.add_parser(
        "capture-aster-depth",
        help="Development/debug: capture Aster depth streams and periodic REST snapshots into raw storage.",
    )
    _add_config_arguments(capture_aster_depth_parser, suppress_defaults=True)
    capture_aster_depth_parser.add_argument(
        "--event-limit",
        type=int,
        default=None,
        help="Optional maximum number of Aster depth events to capture before exiting.",
    )
    capture_aster_depth_parser.add_argument(
        "--duration-seconds",
        type=float,
        default=None,
        help="Optional maximum runtime for the Aster depth capture command.",
    )

    serve_tradingview_parser = subparsers.add_parser(
        "serve-tradingview",
        help="Development/debug: serve the TradingView webhook receiver and write raw alert events.",
    )
    _add_config_arguments(serve_tradingview_parser, suppress_defaults=True)
    serve_tradingview_parser.add_argument(
        "--duration-seconds",
        type=float,
        default=None,
        help="Optional maximum runtime for the TradingView webhook server.",
    )
    serve_tradingview_parser.add_argument(
        "--request-limit",
        type=int,
        default=None,
        help="Optional maximum number of accepted webhook requests before exiting.",
    )
    serve_tradingview_parser.add_argument(
        "--bind-host",
        default=None,
        help="Optional override bind host for the webhook server.",
    )
    serve_tradingview_parser.add_argument(
        "--bind-port",
        type=int,
        default=None,
        help="Optional override bind port for the webhook server.",
    )
    serve_tradingview_parser.add_argument(
        "--path",
        default=None,
        help="Optional override request path for the webhook server.",
    )

    validate_raw_parser = subparsers.add_parser(
        "validate-raw",
        help="Validate an existing raw .jsonl.zst file.",
    )
    validate_raw_parser.add_argument("path", help="Path to the raw .jsonl.zst file to inspect.")

    report_quality_parser = subparsers.add_parser(
        "report-data-quality",
        help="Report missing, stale, or invalid raw routes for the current config.",
    )
    _add_config_arguments(report_quality_parser, suppress_defaults=True)
    report_quality_parser.add_argument(
        "--stale-after-seconds",
        type=float,
        default=900.0,
        help="Maximum acceptable age for the newest raw file on each expected route.",
    )

    worker_parser = subparsers.add_parser(
        "service-worker",
        help=argparse.SUPPRESS,
    )
    _add_config_arguments(worker_parser, suppress_defaults=True)
    _add_service_control_arguments(worker_parser, health_interval_default=10.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.version:
        print(__version__)
        return 0

    command = args.command or "status"

    if args.command == "validate-raw":
        summary = validate_raw_file(Path(args.path))
        print(_format_validation_summary(summary))
        return 0

    if command == "status":
        return _status_command(include_hint=args.command is None)
    if command == "stop":
        return _stop_command()
    if command == "health":
        return _health_command()

    try:
        config = load_config(args.config or DEFAULT_CONFIG_PATH, sources_path=args.sources)
        config = apply_runtime_overrides(
            config,
            data_root=args.data_root,
            log_level=args.log_level,
        )
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    if command == "validate-config":
        print(_format_config_summary(config))
        return 0
    if command == "start":
        return _start_command(config, args)
    if command == "restart":
        return _restart_command(config, args)
    if command == "write-sample":
        print(_write_sample_output(config, args))
        return 0
    if command == "capture-pyth":
        configure_logging(config.logging.level, structured=config.logging.structured)
        return asyncio.run(_capture_pyth_command(config, args))
    if command == "capture-aster":
        configure_logging(config.logging.level, structured=config.logging.structured)
        return asyncio.run(_capture_aster_command(config, args))
    if command == "capture-aster-depth":
        configure_logging(config.logging.level, structured=config.logging.structured)
        return asyncio.run(_capture_aster_depth_command(config, args))
    if command == "serve-tradingview":
        configure_logging(config.logging.level, structured=config.logging.structured)
        return asyncio.run(_serve_tradingview_command(config, args))
    if command == "run-service":
        configure_logging(config.logging.level, structured=config.logging.structured)
        return asyncio.run(_run_service_command(config, args))
    if command == "service-worker":
        configure_logging(config.logging.level, structured=config.logging.structured)
        return asyncio.run(_service_worker_command(config, args))
    if command == "report-data-quality":
        report = build_data_quality_report(config, stale_after_seconds=args.stale_after_seconds)
        print(_format_data_quality_report(report))
        return 0 if _is_quality_report_clean(report) else 1

    configure_logging(config.logging.level, structured=config.logging.structured)
    return asyncio.run(_run_runtime_check(config))


async def _run_runtime_check(config) -> int:
    logger = get_logger("market_recorder.cli")
    async with RecorderRuntime.from_config(config) as runtime:
        logger.info("Runtime initialized for run_id=%s", runtime.run_id)
        print(f"Runtime initialized: {runtime.run_id}")
        print(f"Enabled sources: {_format_enabled_sources(config.enabled_sources)}")
        print("No source tasks are implemented yet.")
    return 0


def _format_config_summary(config) -> str:
    return "\n".join(
        [
            f"Configuration valid: {config.config_path}",
            f"Sources config: {config.sources_path}",
            f"Data root: {config.runtime.data_root}",
            f"Log level: {config.logging.level}",
            f"Enabled sources: {_format_enabled_sources(config.enabled_sources)}",
            f"Storage format: {config.storage.format}",
            f"Rotation: {config.storage.rotation}",
            f"Compression level: {config.storage.compression_level}",
        ],
    )


def _format_enabled_sources(source_names: tuple[str, ...]) -> str:
    return ", ".join(source_names) if source_names else "none"


def _format_validation_summary(summary: RawFileValidationSummary) -> str:
    return "\n".join(
        [
            f"Raw file valid: {summary.path}",
            f"Records: {summary.record_count}",
            f"First timestamp: {summary.first_ts_recv_utc}",
            f"Last timestamp: {summary.last_ts_recv_utc}",
        ],
    )


def _format_pyth_capture_summary(summary: PythCaptureSummary) -> str:
    lines = [
        "Pyth capture complete",
        f"Records: {summary.records_written}",
        f"Reconnects: {summary.reconnect_count}",
        f"Error records: {summary.error_record_count}",
    ]
    for path in summary.output_paths:
        lines.append(f"Output path: {path}")
    return "\n".join(lines)


def _format_aster_capture_summary(summary: AsterCaptureSummary) -> str:
    lines = [
        "Aster capture complete",
        f"Records: {summary.records_written}",
        f"Reconnects: {summary.reconnect_count}",
        f"Error records: {summary.error_record_count}",
    ]
    for path in summary.output_paths:
        lines.append(f"Output path: {path}")
    return "\n".join(lines)


def _format_aster_depth_capture_summary(summary: AsterDepthCaptureSummary) -> str:
    lines = [
        "Aster depth capture complete",
        f"Depth records: {summary.depth_record_count}",
        f"Snapshots: {summary.snapshot_record_count}",
        f"Reconnects: {summary.reconnect_count}",
        f"Continuity restarts: {summary.continuity_restart_count}",
        f"Error records: {summary.error_record_count}",
    ]
    for path in summary.output_paths:
        lines.append(f"Output path: {path}")
    return "\n".join(lines)


def _format_tradingview_summary(summary: TradingViewWebhookSummary) -> str:
    lines = [
        "TradingView webhook server complete",
        f"Requests: {summary.request_count}",
        f"Error records: {summary.error_record_count}",
        f"Bind address: {summary.bind_host}:{summary.bind_port}",
        f"Path: {summary.path}",
    ]
    for path in summary.output_paths:
        lines.append(f"Output path: {path}")
    return "\n".join(lines)


def _format_service_summary(summary: RecorderServiceSummary) -> str:
    lines = [
        "Recorder service run complete",
        f"Run ID: {summary.run_id}",
        f"Started: {summary.started_at_utc}",
        f"Finished: {summary.finished_at_utc}",
        f"Health manifest: {summary.health_path}",
    ]
    for component_name, status in sorted(summary.component_statuses.items()):
        lines.append(f"Component {component_name}: {status}")
    for component_name, observation in sorted(summary.component_outputs.items()):
        lines.append(
            f"Output {component_name}: {observation.file_count} file(s), latest={observation.latest_output_utc}",
        )
    return "\n".join(lines)


def _format_service_status(status: RecorderServiceStatus, *, include_hint: bool = False) -> str:
    lines = [
        "Recorder service status",
        f"State: {status.state}",
        f"Service log: {status.log_path}",
        f"State file: {status.state_path}",
    ]
    if status.pid is not None:
        lines.append(f"PID: {status.pid}")
    if status.run_id is not None:
        lines.append(f"Run ID: {status.run_id}")
    if status.service_state is not None:
        state = status.service_state
        lines.append(f"Config: {state.config_path}")
        lines.append(f"Sources: {state.sources_path}")
        lines.append(f"Data root: {state.data_root}")
        if state.started_at_utc is not None:
            lines.append(f"Started: {state.started_at_utc}")
        lines.append(f"Updated: {state.updated_at_utc}")
        if state.finished_at_utc is not None:
            lines.append(f"Finished: {state.finished_at_utc}")
        if state.health_path is not None:
            lines.append(f"Health manifest: {state.health_path}")
    if status.message:
        lines.append(f"Message: {status.message}")
    if include_hint and not status.is_running:
        lines.append("Hint: run 'market-recorder start' to start the recorder service.")
    return "\n".join(lines)


def _format_service_health(status: RecorderServiceStatus, payload: dict[str, Any] | None) -> str:
    lines = [
        "Recorder service health",
        f"Service state: {status.state}",
    ]
    if status.run_id is not None:
        lines.append(f"Run ID: {status.run_id}")

    state = status.service_state
    if state is not None and state.health_path is not None:
        lines.append(f"Health manifest: {state.health_path}")

    if payload is None:
        lines.append("Health data: unavailable")
        if status.message:
            lines.append(f"Message: {status.message}")
        return "\n".join(lines)

    lines.append(f"Updated: {payload.get('updated_at_utc', 'unknown')}")
    enabled_components = payload.get("enabled_components") or []
    lines.append(
        "Enabled components: " + (", ".join(enabled_components) if enabled_components else "none"),
    )
    component_statuses = payload.get("component_statuses") or {}
    for component_name, component_status in sorted(component_statuses.items()):
        lines.append(f"Component {component_name}: {component_status}")

    component_outputs = payload.get("component_outputs") or {}
    for component_name, observation in sorted(component_outputs.items()):
        latest_output = observation.get("latest_output_utc") if isinstance(observation, dict) else None
        file_count = observation.get("file_count") if isinstance(observation, dict) else None
        lines.append(f"Output {component_name}: {file_count} file(s), latest={latest_output}")
    return "\n".join(lines)


def _format_data_quality_report(report: DataQualityReport) -> str:
    lines = [
        "Data quality report",
        f"Checked routes: {report.checked_route_count}",
        f"OK routes: {report.ok_route_count}",
        f"Missing routes: {report.missing_route_count}",
        f"Stale routes: {report.stale_route_count}",
        f"Invalid routes: {report.invalid_route_count}",
    ]
    for route in report.routes:
        line = f"Route {route.route}: {route.status}"
        if not route.required:
            line += ", optional"
        if route.latest_output_utc is not None:
            line += f", latest={route.latest_output_utc}"
        if route.record_count is not None:
            line += f", records={route.record_count}"
        if route.message:
            line += f", note={route.message}"
        lines.append(line)
    return "\n".join(lines)


def _write_sample_output(config, args: argparse.Namespace) -> str:
    route = RawStreamRoute(
        source=args.source,
        transport=args.transport,
        source_symbol=args.source_symbol,
        stream=args.stream,
    )
    run_id = make_run_id("sample")
    writer = RawJsonlZstWriter(
        data_root=config.runtime.data_root,
        route=route,
        run_id=run_id,
        compression_level=config.storage.compression_level,
    )
    conn_id = f"{run_id}-conn"
    last_path = None
    for seq in (1, 2):
        last_path = writer.write_record(
            build_market_event(
                source=route.source,
                transport=route.transport,
                stream=route.stream,
                stream_name=None,
                canonical_symbol="SAMPLE",
                source_symbol=route.source_symbol,
                conn_id=conn_id,
                seq=seq,
                payload={"kind": "sample", "seq": seq},
            ),
        )
    writer.flush()
    writer.close()

    if last_path is None:
        raise RuntimeError("Sample writer did not produce an output path")

    summary = validate_raw_file(last_path)
    return "\n".join(
        [
            f"Sample raw file: {last_path}",
            f"Records: {summary.record_count}",
            f"Compression level: {config.storage.compression_level}",
        ],
    )


async def _capture_pyth_command(config, args: argparse.Namespace) -> int:
    async with RecorderRuntime.from_config(config) as runtime:
        summary = await capture_pyth(
            runtime=runtime,
            event_limit=args.event_limit,
            duration_seconds=args.duration_seconds,
        )
    print(_format_pyth_capture_summary(summary))
    return 0


async def _capture_aster_command(config, args: argparse.Namespace) -> int:
    async with RecorderRuntime.from_config(config) as runtime:
        summary = await capture_aster(
            runtime=runtime,
            event_limit=args.event_limit,
            duration_seconds=args.duration_seconds,
        )
    print(_format_aster_capture_summary(summary))
    return 0


async def _capture_aster_depth_command(config, args: argparse.Namespace) -> int:
    async with RecorderRuntime.from_config(config) as runtime:
        summary = await capture_aster_depth(
            runtime=runtime,
            event_limit=args.event_limit,
            duration_seconds=args.duration_seconds,
        )
    print(_format_aster_depth_capture_summary(summary))
    return 0


async def _serve_tradingview_command(config, args: argparse.Namespace) -> int:
    runtime = RecorderRuntime.from_config(config)
    try:
        summary = await serve_tradingview_webhook(
            runtime=runtime,
            duration_seconds=args.duration_seconds,
            request_limit=args.request_limit,
            bind_host=args.bind_host,
            bind_port=args.bind_port,
            path=args.path,
        )
    finally:
        await runtime.close()
    print(_format_tradingview_summary(summary))
    return 0


async def _run_service_command(config, args: argparse.Namespace) -> int:
    running_status = read_service_status(REPO_ROOT)
    if running_status.is_running:
        print(_format_service_status(running_status), file=sys.stderr)
        return 1

    runtime = RecorderRuntime.from_config(config)
    try:
        summary = await run_recorder_service(
            runtime=runtime,
            duration_seconds=args.duration_seconds,
            health_interval_seconds=args.health_interval_seconds,
            health_path=Path(args.health_path) if args.health_path else None,
        )
    finally:
        await runtime.close()
    print(_format_service_summary(summary))
    return 0


async def _service_worker_command(config, args: argparse.Namespace) -> int:
    return await run_service_worker_foreground(
        config,
        health_interval_seconds=args.health_interval_seconds,
        health_path=Path(args.health_path) if args.health_path else None,
        duration_seconds=args.duration_seconds,
    )


def _add_config_arguments(
    parser: argparse.ArgumentParser,
    *,
    suppress_defaults: bool = False,
) -> None:
    default_value = argparse.SUPPRESS if suppress_defaults else None
    parser.add_argument(
        "--config",
        default=default_value,
        help="Path to the runtime config file.",
    )
    parser.add_argument(
        "--sources",
        default=default_value,
        help="Optional override path to the sources config file.",
    )
    parser.add_argument(
        "--data-root",
        default=default_value,
        help="Optional override data root for this invocation.",
    )
    parser.add_argument(
        "--log-level",
        default=default_value,
        help="Optional override log level for this invocation.",
    )


def _add_service_control_arguments(
    parser: argparse.ArgumentParser,
    *,
    health_interval_default: float | None = None,
) -> None:
    parser.add_argument(
        "--duration-seconds",
        type=float,
        default=None,
        help="Optional maximum runtime for the recorder service.",
    )
    parser.add_argument(
        "--health-interval-seconds",
        type=float,
        default=health_interval_default,
        help="Optional interval for writing the runtime health manifest.",
    )
    parser.add_argument(
        "--health-path",
        default=None,
        help="Optional override path for the runtime health manifest JSON file.",
    )


def _status_command(*, include_hint: bool = False) -> int:
    try:
        status = read_service_status(REPO_ROOT)
    except ServiceControlError as exc:
        print(f"Service control error: {exc}", file=sys.stderr)
        return 1

    print(_format_service_status(status, include_hint=include_hint))
    return 0 if status.is_running else 1


def _stop_command() -> int:
    try:
        status = stop_background_service(REPO_ROOT)
    except ServiceControlError as exc:
        print(f"Service control error: {exc}", file=sys.stderr)
        return 1

    print(_format_service_status(status))
    return 0


def _health_command() -> int:
    try:
        status, payload = load_service_health(REPO_ROOT)
    except ServiceControlError as exc:
        print(f"Service control error: {exc}", file=sys.stderr)
        return 1

    print(_format_service_health(status, payload))
    return 0 if status.is_running and payload is not None else 1


def _start_command(config, args: argparse.Namespace) -> int:
    try:
        launch_spec = _build_launch_spec(config, args)
        status = start_background_service(launch_spec)
    except ServiceControlError as exc:
        print(f"Service control error: {exc}", file=sys.stderr)
        return 1

    print(_format_service_status(status))
    return 0


def _restart_command(config, args: argparse.Namespace) -> int:
    try:
        current_status = read_service_status(REPO_ROOT)
        if current_status.is_running:
            stop_background_service(REPO_ROOT)

        launch_spec = _build_restart_launch_spec(config, args, current_status)
        status = start_background_service(launch_spec)
    except ServiceControlError as exc:
        print(f"Service control error: {exc}", file=sys.stderr)
        return 1

    print(_format_service_status(status))
    return 0


def _build_launch_spec(config, args: argparse.Namespace) -> RecorderServiceLaunchSpec:
    return build_service_launch_spec(
        config,
        health_interval_seconds=args.health_interval_seconds,
        health_path=args.health_path,
        duration_seconds=args.duration_seconds,
    )


def _build_restart_launch_spec(
    config,
    args: argparse.Namespace,
    current_status: RecorderServiceStatus,
) -> RecorderServiceLaunchSpec:
    if not _has_service_start_overrides(args) and current_status.service_state is not None:
        return current_status.service_state.to_launch_spec()
    return _build_launch_spec(config, args)


def _has_service_start_overrides(args: argparse.Namespace) -> bool:
    return any(
            value is not None
            for value in (
                args.config,
                args.sources,
                args.data_root,
                args.log_level,
                args.health_interval_seconds,
                args.health_path,
                args.duration_seconds,
            )
    )


def _is_quality_report_clean(report: DataQualityReport) -> bool:
    return report.missing_route_count == 0 and report.stale_route_count == 0 and report.invalid_route_count == 0


if __name__ == "__main__":
    raise SystemExit(main())