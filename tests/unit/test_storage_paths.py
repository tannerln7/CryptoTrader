from __future__ import annotations

from pathlib import Path

from market_recorder.storage import (
    RawStreamRoute,
    build_active_raw_segment_path,
    build_raw_stream_directory,
    build_sealed_raw_segment_path,
    parse_utc_timestamp,
)


def test_build_raw_stream_directory_preserves_per_stream_layout() -> None:
    path = build_raw_stream_directory(
        data_root=Path("/tmp/data"),
        route=RawStreamRoute(
            source="aster",
            transport="ws",
            source_symbol="BTCUSDT",
            stream="markPrice@1s",
        ),
        segment_start=parse_utc_timestamp("2026-04-30T14:00:00Z"),
    )

    assert path == Path(
        "/tmp/data/raw/aster/ws/BTCUSDT/markPrice_1s/date=2026-04-30/hour=14",
    )


def test_build_segment_paths_use_segment_times_and_sanitized_route() -> None:
    route = RawStreamRoute(
        source="aster",
        transport="ws",
        source_symbol="BTCUSDT",
        stream="depth@100ms",
    )
    segment_start = parse_utc_timestamp("2026-04-30T14:00:00Z")
    segment_end = parse_utc_timestamp("2026-04-30T15:00:00Z")

    active_path = build_active_raw_segment_path(
        data_root=Path("/tmp/data"),
        route=route,
        segment_start=segment_start,
        run_id="run-123",
    )
    sealed_path = build_sealed_raw_segment_path(
        data_root=Path("/tmp/data"),
        route=route,
        segment_start=segment_start,
        segment_end=segment_end,
        run_id="run-123",
    )

    assert active_path == Path(
        "/tmp/data/raw/aster/ws/BTCUSDT/depth_100ms/date=2026-04-30/hour=14/part-20260430T140000Z-run-123.jsonl.zst.open",
    )
    assert sealed_path == Path(
        "/tmp/data/raw/aster/ws/BTCUSDT/depth_100ms/date=2026-04-30/hour=14/part-20260430T140000Z-20260430T150000Z-run-123.jsonl.zst",
    )