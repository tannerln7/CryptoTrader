"""Canonical raw data path generation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_INVALID_PATH_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True, slots=True)
class RawStreamRoute:
    source: str
    transport: str
    source_symbol: str
    stream: str


def sanitize_path_component(value: str) -> str:
    normalized = _INVALID_PATH_CHARS.sub("_", value.strip())
    normalized = normalized.strip("._")
    if not normalized:
        raise ValueError(f"Path component {value!r} is empty after sanitization")
    return normalized


def parse_utc_timestamp(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    timestamp = datetime.fromisoformat(normalized)
    if timestamp.tzinfo is None:
        raise ValueError("ts_recv_utc must be timezone-aware")
    return timestamp.astimezone(timezone.utc)


def build_raw_file_path(
    *,
    data_root: Path,
    route: RawStreamRoute,
    ts_recv_utc: str,
    run_id: str,
) -> Path:
    timestamp = parse_utc_timestamp(ts_recv_utc)
    return (
        data_root
        / "raw"
        / sanitize_path_component(route.source)
        / sanitize_path_component(route.transport)
        / sanitize_path_component(route.source_symbol)
        / sanitize_path_component(route.stream)
        / f"date={timestamp:%Y-%m-%d}"
        / f"hour={timestamp:%H}"
        / f"part-{sanitize_path_component(run_id)}.jsonl.zst"
    )