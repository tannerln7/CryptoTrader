from __future__ import annotations

from market_recorder.contracts import build_market_event, build_recorder_error


def test_build_market_event_matches_expected_schema() -> None:
    envelope = build_market_event(
        source="pyth",
        transport="sse",
        stream="price_stream",
        stream_name=None,
        canonical_symbol="BTCUSD",
        source_symbol="BTC/USD",
        conn_id="pyth-conn-1",
        seq=1,
        payload={"price": "100000.00"},
    )

    assert envelope["schema"] == "raw.market_event.v1"
    assert envelope["source"] == "pyth"
    assert envelope["ts_recv_utc"].endswith("Z")
    assert isinstance(envelope["ts_recv_ns"], int)
    assert isinstance(envelope["monotonic_ns"], int)


def test_build_recorder_error_uses_error_schema() -> None:
    envelope = build_recorder_error(
        source="aster",
        transport="ws",
        stream="aggTrade",
        stream_name="btcusdt@aggTrade",
        canonical_symbol="BTCUSD",
        source_symbol="BTCUSDT",
        conn_id="aster-conn-1",
        seq=7,
        payload={"message": "stream disconnected"},
    )

    assert envelope["schema"] == "raw.recorder_error.v1"
    assert envelope["payload"]["message"] == "stream disconnected"