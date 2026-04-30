"""Streaming raw file validation utilities."""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import zstandard

ACTIVE_RAW_FILE_SUFFIX = ".jsonl.zst.open"
SEALED_RAW_FILE_SUFFIX = ".jsonl.zst"

REQUIRED_RAW_FIELDS = frozenset(
    {
        "schema",
        "source",
        "transport",
        "stream",
        "canonical_symbol",
        "source_symbol",
        "ts_recv_ns",
        "ts_recv_utc",
        "monotonic_ns",
        "conn_id",
        "seq",
        "payload",
    },
)


@dataclass(frozen=True, slots=True)
class RawFileValidationSummary:
    path: Path
    record_count: int
    first_ts_recv_utc: str | None
    last_ts_recv_utc: str | None


def is_active_raw_file(path: Path) -> bool:
    return path.name.endswith(ACTIVE_RAW_FILE_SUFFIX)


def is_sealed_raw_file(path: Path) -> bool:
    return path.name.endswith(SEALED_RAW_FILE_SUFFIX) and not is_active_raw_file(path)


def iter_raw_records(path: Path, *, allow_active: bool = False) -> Iterator[dict[str, Any]]:
    _ensure_raw_file_is_readable(path, allow_active=allow_active)
    with zstandard.open(path, mode="rt", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                record = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_number} of {path}") from exc
            if not isinstance(record, dict):
                raise ValueError(f"Record {line_number} in {path} is not a JSON object")
            yield record


def validate_raw_file(path: Path, *, allow_active: bool = False) -> RawFileValidationSummary:
    record_count = 0
    first_ts_recv_utc: str | None = None
    last_ts_recv_utc: str | None = None

    for record_count, record in enumerate(iter_raw_records(path, allow_active=allow_active), start=1):
        _validate_required_fields(record=record, path=path, line_number=record_count)
        current_timestamp = record["ts_recv_utc"]
        if first_ts_recv_utc is None:
            first_ts_recv_utc = current_timestamp
        last_ts_recv_utc = current_timestamp

    if record_count == 0:
        raise ValueError(f"Raw file contains no records: {path}")

    return RawFileValidationSummary(
        path=path,
        record_count=record_count,
        first_ts_recv_utc=first_ts_recv_utc,
        last_ts_recv_utc=last_ts_recv_utc,
    )


def _ensure_raw_file_is_readable(path: Path, *, allow_active: bool) -> None:
    if is_active_raw_file(path) and not allow_active:
        raise ValueError(f"Refusing to validate active raw segment by default: {path}")


def _validate_required_fields(*, path: Path, line_number: int, record: Mapping[str, Any]) -> None:
    missing_fields = REQUIRED_RAW_FIELDS.difference(record)
    if missing_fields:
        missing = ", ".join(sorted(missing_fields))
        raise ValueError(f"Missing required raw fields on line {line_number} of {path}: {missing}")