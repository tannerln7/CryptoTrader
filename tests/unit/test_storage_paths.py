from __future__ import annotations

from pathlib import Path

from market_recorder.storage import RawStreamRoute, build_raw_file_path


def test_build_raw_file_path_uses_canonical_partition_layout() -> None:
    path = build_raw_file_path(
        data_root=Path("/tmp/data"),
        route=RawStreamRoute(
            source="aster",
            transport="ws",
            source_symbol="BTCUSDT",
            stream="markPrice@1s",
        ),
        ts_recv_utc="2026-04-30T14:15:16Z",
        run_id="run-123",
    )

    assert path == Path(
        "/tmp/data/raw/aster/ws/BTCUSDT/markPrice_1s/date=2026-04-30/hour=14/part-run-123.jsonl.zst",
    )