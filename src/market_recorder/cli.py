"""Minimal CLI entrypoint for the Phase 0 scaffold."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from . import __version__
from .config import DEFAULT_CONFIG_PATH, DEFAULT_SOURCES_PATH


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="market-recorder",
        description="Phase 0 scaffold for the market recorder workspace.",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Print the scaffold package version and exit.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.version:
        print(__version__)
        return 0

    print("Phase 0 scaffold only. No recorder behavior is implemented yet.")
    print(f"Default runtime config: {DEFAULT_CONFIG_PATH}")
    print(f"Default sources config: {DEFAULT_SOURCES_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())