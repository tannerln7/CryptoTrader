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


def format_compact_utc(value: datetime) -> str:
    timestamp = _require_utc_datetime(value, name="value")
    if timestamp.microsecond:
        return timestamp.strftime("%Y%m%dT%H%M%S") + f"{timestamp.microsecond:06d}Z"
    return timestamp.strftime("%Y%m%dT%H%M%SZ")


def build_raw_stream_directory(
    *,
    data_root: Path,
    route: RawStreamRoute,
    segment_start: datetime,
) -> Path:
    timestamp = _require_utc_datetime(segment_start, name="segment_start")
    return (
        data_root
        / "raw"
        / sanitize_path_component(route.source)
        / sanitize_path_component(route.transport)
        / sanitize_path_component(route.source_symbol)
        / sanitize_path_component(route.stream)
        / f"date={timestamp:%Y-%m-%d}"
        / f"hour={timestamp:%H}"
    )


def build_active_raw_segment_path(
    *,
    data_root: Path,
    route: RawStreamRoute,
    segment_start: datetime,
    run_id: str,
) -> Path:
    return build_raw_stream_directory(
        data_root=data_root,
        route=route,
        segment_start=segment_start,
    ) / f"part-{format_compact_utc(segment_start)}-{sanitize_path_component(run_id)}.jsonl.zst.open"


def build_sealed_raw_segment_path(
    *,
    data_root: Path,
    route: RawStreamRoute,
    segment_start: datetime,
    segment_end: datetime,
    run_id: str,
) -> Path:
    return build_raw_stream_directory(
        data_root=data_root,
        route=route,
        segment_start=segment_start,
    ) / (
        f"part-{format_compact_utc(segment_start)}-"
        f"{format_compact_utc(segment_end)}-"
        f"{sanitize_path_component(run_id)}.jsonl.zst"
    )


def _require_utc_datetime(value: datetime, *, name: str) -> datetime:
    if value.tzinfo is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)