from __future__ import annotations

from market_recorder.config import load_config
from market_recorder.sources.aster import (
    build_aster_combined_stream_url,
    build_aster_stream_targets,
)


def test_build_aster_stream_targets_filters_depth_streams_and_lowercases_names() -> None:
    targets = build_aster_stream_targets(load_config().sources.aster)
    stream_names = {target.stream_name for target in targets}
    logical_streams = {target.logical_stream for target in targets}

    assert "depth20@100ms" not in logical_streams
    assert "depth@100ms" not in logical_streams
    assert "btcusdt@aggTrade" in stream_names
    assert "ethusdt@bookTicker" in stream_names
    assert "btcusdt@markPrice@1s" in stream_names


def test_build_aster_combined_stream_url_uses_combined_stream_path() -> None:
    targets = build_aster_stream_targets(load_config().sources.aster)
    url = build_aster_combined_stream_url("wss://fstream.asterdex.com", targets)

    assert url.startswith("wss://fstream.asterdex.com/stream?streams=")
    assert "btcusdt@aggTrade" in url
    assert "ethusdt@kline_15m" in url