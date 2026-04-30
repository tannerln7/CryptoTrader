from __future__ import annotations

from pathlib import Path

from market_recorder.contracts import build_market_event
from market_recorder.storage import RawJsonlZstWriter, RawStreamRoute, validate_raw_file


def test_writer_flush_makes_current_file_readable_before_close(tmp_path: Path) -> None:
    route = RawStreamRoute(source="sample", transport="internal", source_symbol="BTCUSD", stream="price_stream")
    writer = RawJsonlZstWriter(
        data_root=tmp_path,
        route=route,
        run_id="sample-run",
        compression_level=3,
    )

    path = writer.write_record(
        build_market_event(
            source=route.source,
            transport=route.transport,
            stream=route.stream,
            stream_name=None,
            canonical_symbol="BTCUSD",
            source_symbol=route.source_symbol,
            conn_id="sample-conn",
            seq=1,
            payload={"price": "1"},
            ts_recv_ns=1,
            ts_recv_utc="2026-04-30T14:00:00Z",
            monotonic_value=1,
        ),
    )
    writer.flush()

    summary = validate_raw_file(path)
    assert summary.record_count == 1

    writer.close()


def test_writer_rotates_when_hour_partition_changes(tmp_path: Path) -> None:
    route = RawStreamRoute(source="sample", transport="internal", source_symbol="BTCUSD", stream="price_stream")
    writer = RawJsonlZstWriter(
        data_root=tmp_path,
        route=route,
        run_id="sample-run",
        compression_level=3,
    )

    first_path = writer.write_record(
        build_market_event(
            source=route.source,
            transport=route.transport,
            stream=route.stream,
            stream_name=None,
            canonical_symbol="BTCUSD",
            source_symbol=route.source_symbol,
            conn_id="sample-conn",
            seq=1,
            payload={"price": "1"},
            ts_recv_ns=1,
            ts_recv_utc="2026-04-30T14:00:00Z",
            monotonic_value=1,
        ),
    )
    second_path = writer.write_record(
        build_market_event(
            source=route.source,
            transport=route.transport,
            stream=route.stream,
            stream_name=None,
            canonical_symbol="BTCUSD",
            source_symbol=route.source_symbol,
            conn_id="sample-conn",
            seq=2,
            payload={"price": "2"},
            ts_recv_ns=2,
            ts_recv_utc="2026-04-30T15:00:00Z",
            monotonic_value=2,
        ),
    )

    writer.close()

    assert first_path != second_path
    assert validate_raw_file(first_path).record_count == 1
    assert validate_raw_file(second_path).record_count == 1