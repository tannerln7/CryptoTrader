"""CLI entrypoints for configuration checks and runtime bootstrap."""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Sequence

from . import __version__
from .config import DEFAULT_CONFIG_PATH, ConfigError, load_config
from .logging import configure_logging, get_logger
from .runtime import RecorderRuntime


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

    run_parser = subparsers.add_parser(
        "run",
        help="Initialize the runtime skeleton and exit after startup checks.",
    )
    _add_config_arguments(run_parser)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.version:
        print(__version__)
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
        ],
    )


def _format_enabled_sources(source_names: tuple[str, ...]) -> str:
    return ", ".join(source_names) if source_names else "none"


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