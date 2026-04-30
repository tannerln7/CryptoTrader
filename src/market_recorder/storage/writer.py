"""Streaming raw JSONL writer with hourly rotation."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, BinaryIO

import zstandard

from .paths import RawStreamRoute, build_raw_file_path


class RawJsonlZstWriter:
    """Write raw envelope records to canonical hourly JSONL Zstandard files."""

    def __init__(
        self,
        *,
        data_root: Path,
        route: RawStreamRoute,
        run_id: str,
        compression_level: int = 3,
    ) -> None:
        self.data_root = data_root
        self.route = route
        self.run_id = run_id
        self.compression_level = compression_level
        self._current_path: Path | None = None
        self._file_handle: BinaryIO | None = None
        self._writer: zstandard.ZstdCompressionWriter | None = None

    @property
    def current_path(self) -> Path | None:
        return self._current_path


    def write_record(self, record: Mapping[str, Any]) -> Path:
        ts_recv_utc = _require_ts_recv_utc(record)
        next_path = build_raw_file_path(
            data_root=self.data_root,
            route=self.route,
            ts_recv_utc=ts_recv_utc,
            run_id=self.run_id,
        )
        if self._current_path != next_path:
            self._rotate(next_path)

        if self._writer is None:
            raise RuntimeError("Writer is not open")

        line = json.dumps(record, separators=(",", ":"), sort_keys=False).encode("utf-8") + b"\n"
        self._writer.write(line)
        return next_path


    def flush(self) -> None:
        if self._writer is None:
            return
        self._writer.flush(zstandard.FLUSH_BLOCK)
        if self._file_handle is not None and not self._file_handle.closed:
            self._file_handle.flush()


    def close(self) -> None:
        if self._writer is None:
            return
        self._writer.flush(zstandard.FLUSH_FRAME)
        self._writer.close()
        if self._file_handle is not None and not self._file_handle.closed:
            self._file_handle.close()
        self._writer = None
        self._file_handle = None
        self._current_path = None


    def _rotate(self, next_path: Path) -> None:
        self.close()
        next_path.parent.mkdir(parents=True, exist_ok=True)
        self._file_handle = next_path.open("xb")
        compressor = zstandard.ZstdCompressor(level=self.compression_level, write_checksum=True)
        self._writer = compressor.stream_writer(self._file_handle)
        self._current_path = next_path


def _require_ts_recv_utc(record: Mapping[str, Any]) -> str:
    value = record.get("ts_recv_utc")
    if not isinstance(value, str) or not value:
        raise ValueError("Raw records must contain a non-empty ts_recv_utc field")
    return value