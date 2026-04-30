"""CLI entrypoints for configuration checks and runtime bootstrap."""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Sequence
from pathlib import Path

from . import __version__
from .config import DEFAULT_CONFIG_PATH, ConfigError, load_config
from .contracts import build_market_event
from .logging import configure_logging, get_logger
from .runtime import RecorderRuntime
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
        description="Phase 1 runtime contracts and recorder skeleton.",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Print the recorder package version and exit.",
    )
    _add_config_arguments(parser)

    subparsers = parser.add_subparsers(dest="command")
    validate_config_parser = subparsers.add_parser(
        "validate-config",
        help="Load and validate the runtime and sources config.",
    )
    _add_config_arguments(validate_config_parser)

    write_sample_parser = subparsers.add_parser(
        "write-sample",
        help="Write a sample raw .jsonl.zst file under the configured data root.",
    )
    _add_config_arguments(write_sample_parser)
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
        help="Initialize the runtime skeleton and exit after startup checks.",
    )
    _add_config_arguments(run_parser)

    validate_raw_parser = subparsers.add_parser(
        "validate-raw",
        help="Validate an existing raw .jsonl.zst file.",
    )
    validate_raw_parser.add_argument("path", help="Path to the raw .jsonl.zst file to inspect.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.version:
        print(__version__)
        return 0

    if args.command == "validate-raw":
        summary = validate_raw_file(Path(args.path))
        print(_format_validation_summary(summary))
        return 0

    try:
        config = load_config(args.config, sources_path=args.sources)
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    command = args.command or "run"
    if command == "validate-config":
        print(_format_config_summary(config))
        return 0
    if command == "write-sample":
        print(_write_sample_output(config, args))
        return 0

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


def _add_config_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="Path to the runtime config file.",
    )
    parser.add_argument(
        "--sources",
        default=None,
        help="Optional override path to the sources config file.",
    )


if __name__ == "__main__":
    raise SystemExit(main())