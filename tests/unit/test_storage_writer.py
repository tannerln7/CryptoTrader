from __future__ import annotations

import stat
from pathlib import Path

import pytest

from market_recorder.config import RotationPolicyConfig
from market_recorder.contracts import build_market_event
from market_recorder.storage import RawJsonlZstWriter, RawStreamRoute, validate_raw_file


def test_writer_uses_active_open_path_and_refuses_validation_before_seal(tmp_path: Path) -> None:
    route = RawStreamRoute(source="sample", transport="internal", source_symbol="BTCUSD", stream="price_stream")
    writer = RawJsonlZstWriter(
        data_root=tmp_path,
        route=route,
        run_id="sample-run",
        compression_level=3,
    )

    path = writer.write_record(_build_record(route, seq=1, ts_recv_utc="2026-04-30T14:00:00Z"))
    writer.flush()

    assert path.exists()
    assert path.name.endswith(".jsonl.zst.open")
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    with pytest.raises(ValueError, match="Refusing to validate active raw segment"):
        validate_raw_file(path)

    writer.close()

    sealed_path = writer.sealed_segments[0].sealed_path
    assert stat.S_IMODE(sealed_path.stat().st_mode) == 0o640
    assert validate_raw_file(sealed_path).record_count == 1


def test_writer_seal_returns_segment_metadata_and_renames_file(tmp_path: Path) -> None:
    route = RawStreamRoute(source="sample", transport="internal", source_symbol="BTCUSD", stream="price_stream")
    writer = RawJsonlZstWriter(
        data_root=tmp_path,
        route=route,
        run_id="sample-run",
        compression_level=3,
    )

    active_path = writer.write_record(_build_record(route, seq=1, ts_recv_utc="2026-04-30T14:05:00Z"))
    sealed_segment = writer.seal("manual_test")

    assert sealed_segment is not None
    assert sealed_segment.active_path == active_path
    assert not active_path.exists()
    assert sealed_segment.sealed_path.exists()
    assert sealed_segment.segment_start_utc == "20260430T140000Z"
    assert sealed_segment.segment_end_utc.endswith("Z")
    assert sealed_segment.first_record_ts_recv_utc == "2026-04-30T14:05:00Z"
    assert sealed_segment.last_record_ts_recv_utc == "2026-04-30T14:05:00Z"
    assert sealed_segment.record_count == 1
    assert sealed_segment.file_size_bytes > 0
    assert sealed_segment.seal_reason == "manual_test"
    assert validate_raw_file(sealed_segment.sealed_path).record_count == 1


def test_writer_rotates_when_age_bucket_changes_and_moves_trigger_record_to_new_segment(tmp_path: Path) -> None:
    route = RawStreamRoute(source="sample", transport="internal", source_symbol="BTCUSD", stream="price_stream")
    writer = RawJsonlZstWriter(
        data_root=tmp_path,
        route=route,
        run_id="sample-run",
        compression_level=3,
        rotation_policy=RotationPolicyConfig(max_age_seconds=3600, max_bytes=None),
    )

    writer.write_record(_build_record(route, seq=1, ts_recv_utc="2026-04-30T14:59:59Z"))
    trigger_path = writer.write_record(_build_record(route, seq=2, ts_recv_utc="2026-04-30T15:00:00Z"))

    assert trigger_path.name.endswith(".jsonl.zst.open")
    assert "hour=15" in str(trigger_path)
    assert len(writer.sealed_segments) == 1
    assert writer.sealed_segments[0].seal_reason == "time_rotation"
    assert validate_raw_file(writer.sealed_segments[0].sealed_path).record_count == 1

    writer.close()

    assert len(writer.sealed_segments) == 2
    assert writer.sealed_segments[1].first_record_ts_recv_utc == "2026-04-30T15:00:00Z"
    assert writer.sealed_segments[1].last_record_ts_recv_utc == "2026-04-30T15:00:00Z"
    assert validate_raw_file(writer.sealed_segments[1].sealed_path).record_count == 1


def test_writer_rotates_when_compressed_size_limit_is_reached(tmp_path: Path) -> None:
    route = RawStreamRoute(source="sample", transport="internal", source_symbol="BTCUSD", stream="price_stream")
    writer = RawJsonlZstWriter(
        data_root=tmp_path,
        route=route,
        run_id="sample-run",
        compression_level=3,
        rotation_policy=RotationPolicyConfig(max_age_seconds=3600, max_bytes=1),
    )

    sealed_path = writer.write_record(_build_record(route, seq=1, ts_recv_utc="2026-04-30T14:00:00Z"))

    assert sealed_path.exists()
    assert sealed_path.name.endswith(".jsonl.zst")
    assert writer.current_path is None
    assert len(writer.sealed_segments) == 1
    assert writer.sealed_segments[0].seal_reason == "size_rotation"
    assert validate_raw_file(sealed_path).record_count == 1


def _build_record(route: RawStreamRoute, *, seq: int, ts_recv_utc: str) -> dict[str, object]:
    return build_market_event(
        source=route.source,
        transport=route.transport,
        stream=route.stream,
        stream_name=None,
        canonical_symbol="BTCUSD",
        source_symbol=route.source_symbol,
        conn_id="sample-conn",
        seq=seq,
        payload={"price": str(seq)},
        ts_recv_ns=seq,
        ts_recv_utc=ts_recv_utc,
        monotonic_value=seq,
    )