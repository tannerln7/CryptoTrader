"""Streaming raw JSONL writer with active/sealed segment rotation."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO

import zstandard

from ..config import RotationPolicyConfig
from .paths import (
    RawStreamRoute,
    build_active_raw_segment_path,
    build_sealed_raw_segment_path,
    format_compact_utc,
    parse_utc_timestamp,
)


@dataclass(frozen=True, slots=True)
class RawSegmentSealResult:
    active_path: Path
    sealed_path: Path
    segment_start_utc: str
    segment_end_utc: str
    first_record_ts_recv_utc: str | None
    last_record_ts_recv_utc: str | None
    record_count: int
    file_size_bytes: int
    seal_reason: str
    run_id: str
    route: RawStreamRoute


class RawJsonlZstWriter:
    """Write raw envelope records to per-route active and sealed Zstandard segments."""

    def __init__(
        self,
        *,
        data_root: Path,
        route: RawStreamRoute,
        run_id: str,
        compression_level: int = 3,
        rotation_policy: RotationPolicyConfig | None = None,
    ) -> None:
        self.data_root = data_root
        self.route = route
        self.run_id = run_id
        self.compression_level = compression_level
        self.rotation_policy = rotation_policy or RotationPolicyConfig.hourly_default()
        self._current_path: Path | None = None
        self._file_handle: BinaryIO | None = None
        self._writer: zstandard.ZstdCompressionWriter | None = None
        self._segment_start: datetime | None = None
        self._first_record_ts_recv_utc: str | None = None
        self._last_record_ts_recv_utc: str | None = None
        self._record_count = 0
        self._active_file_size_bytes = 0
        self._sealed_segments: list[RawSegmentSealResult] = []

    @property
    def current_path(self) -> Path | None:
        return self._current_path


    @property
    def sealed_segments(self) -> tuple[RawSegmentSealResult, ...]:
        return tuple(self._sealed_segments)


    def write_record(self, record: Mapping[str, Any]) -> Path:
        ts_recv_utc = _require_ts_recv_utc(record)
        record_timestamp = parse_utc_timestamp(ts_recv_utc)
        segment_start = _segment_start_for_timestamp(
            record_timestamp,
            max_age_seconds=self.rotation_policy.max_age_seconds,
        )
        if self._segment_start != segment_start:
            if self._segment_start is not None:
                self.seal("time_rotation")
            self._open_segment(segment_start)

        if self._writer is None:
            raise RuntimeError("Writer is not open")
        if self._current_path is None:
            raise RuntimeError("Active segment path is not set")

        line = json.dumps(record, separators=(",", ":"), sort_keys=False).encode("utf-8") + b"\n"
        self._writer.write(line)
        if self._first_record_ts_recv_utc is None:
            self._first_record_ts_recv_utc = ts_recv_utc
        self._last_record_ts_recv_utc = ts_recv_utc
        self._record_count += 1

        record_path = self._current_path
        if self.rotation_policy.max_bytes is not None:
            self.flush()
            if self._active_file_size_bytes >= self.rotation_policy.max_bytes:
                sealed_segment = self.seal("size_rotation")
                if sealed_segment is None:
                    raise RuntimeError("Active segment disappeared before size-based seal completed")
                return sealed_segment.sealed_path

        return record_path


    def flush(self) -> None:
        if self._writer is None:
            return
        self._writer.flush(zstandard.FLUSH_BLOCK)
        if self._file_handle is not None and not self._file_handle.closed:
            self._file_handle.flush()
            self._active_file_size_bytes = self._file_handle.tell()


    def close(self) -> None:
        self.seal("close")


    def seal(self, reason: str) -> RawSegmentSealResult | None:
        if self._writer is None or self._file_handle is None or self._current_path is None or self._segment_start is None:
            return None

        active_path = self._current_path
        segment_start = self._segment_start
        self._writer.flush(zstandard.FLUSH_FRAME)
        self._writer.close()
        if not self._file_handle.closed:
            self._file_handle.close()

        segment_end = datetime.now(timezone.utc)
        sealed_path = build_sealed_raw_segment_path(
            data_root=self.data_root,
            route=self.route,
            segment_start=segment_start,
            segment_end=segment_end,
            run_id=self.run_id,
        )
        os.replace(active_path, sealed_path)
        os.chmod(sealed_path, 0o640)
        file_size_bytes = sealed_path.stat().st_size
        sealed_segment = RawSegmentSealResult(
            active_path=active_path,
            sealed_path=sealed_path,
            segment_start_utc=format_compact_utc(segment_start),
            segment_end_utc=format_compact_utc(segment_end),
            first_record_ts_recv_utc=self._first_record_ts_recv_utc,
            last_record_ts_recv_utc=self._last_record_ts_recv_utc,
            record_count=self._record_count,
            file_size_bytes=file_size_bytes,
            seal_reason=reason,
            run_id=self.run_id,
            route=self.route,
        )
        self._sealed_segments.append(sealed_segment)
        self._reset_active_state()
        return sealed_segment


    def _open_segment(self, segment_start: datetime) -> None:
        next_path = build_active_raw_segment_path(
            data_root=self.data_root,
            route=self.route,
            segment_start=segment_start,
            run_id=self.run_id,
        )
        next_path.parent.mkdir(parents=True, exist_ok=True)
        self._file_handle = next_path.open("xb")
        os.fchmod(self._file_handle.fileno(), 0o600)
        compressor = zstandard.ZstdCompressor(level=self.compression_level, write_checksum=True)
        self._writer = compressor.stream_writer(self._file_handle)
        self._current_path = next_path
        self._segment_start = segment_start
        self._first_record_ts_recv_utc = None
        self._last_record_ts_recv_utc = None
        self._record_count = 0
        self._active_file_size_bytes = 0


    def _reset_active_state(self) -> None:
        self._writer = None
        self._file_handle = None
        self._current_path = None
        self._segment_start = None
        self._first_record_ts_recv_utc = None
        self._last_record_ts_recv_utc = None
        self._record_count = 0
        self._active_file_size_bytes = 0


def _segment_start_for_timestamp(timestamp: datetime, *, max_age_seconds: int) -> datetime:
    bucket_start = int(timestamp.timestamp()) // max_age_seconds * max_age_seconds
    return datetime.fromtimestamp(bucket_start, tz=timezone.utc)


def _require_ts_recv_utc(record: Mapping[str, Any]) -> str:
    value = record.get("ts_recv_utc")
    if not isinstance(value, str) or not value:
        raise ValueError("Raw records must contain a non-empty ts_recv_utc field")
    return value