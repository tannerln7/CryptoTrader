from __future__ import annotations

from market_recorder.config import load_config
from market_recorder.sources.aster_depth import (
	build_aster_depth_combined_stream_url,
	build_aster_depth_stream_targets,
	observe_diff_depth_continuity,
)


def test_build_aster_depth_stream_targets_filters_non_depth_streams() -> None:
	targets = build_aster_depth_stream_targets(load_config().sources.aster)
	stream_names = {target.stream_name for target in targets}
	logical_streams = {target.logical_stream for target in targets}
	stream_kinds = {target.logical_stream: target.stream_kind for target in targets}

	assert "aggTrade" not in logical_streams
	assert "bookTicker" not in logical_streams
	assert "btcusdt@depth20@100ms" in stream_names
	assert "ethusdt@depth@100ms" in stream_names
	assert stream_kinds["depth20@100ms"] == "partial"
	assert stream_kinds["depth@100ms"] == "diff"


def test_build_aster_depth_combined_stream_url_uses_combined_stream_path() -> None:
	targets = build_aster_depth_stream_targets(load_config().sources.aster)
	url = build_aster_depth_combined_stream_url("wss://fstream.asterdex.com", targets)

	assert url.startswith("wss://fstream.asterdex.com/stream?streams=")
	assert "btcusdt@depth20@100ms" in url
	assert "ethusdt@depth@100ms" in url


def test_observe_diff_depth_continuity_requires_restart_on_pu_gap() -> None:
	payload = {
		"stream": "btcusdt@depth@100ms",
		"data": {"U": 102, "u": 105, "pu": 100, "b": [], "a": []},
	}

	check = observe_diff_depth_continuity(previous_u=101, payload=payload)

	assert check.current_u == 105
	assert check.observed_pu == 100
	assert check.requires_restart is True
	assert check.reason == "pu_mismatch"


def test_observe_diff_depth_continuity_accepts_matching_pu() -> None:
	payload = {
		"stream": "btcusdt@depth@100ms",
		"data": {"U": 102, "u": 105, "pu": 101, "b": [], "a": []},
	}

	check = observe_diff_depth_continuity(previous_u=101, payload=payload)

	assert check.current_u == 105
	assert check.observed_pu == 101
	assert check.requires_restart is False
	assert check.reason is None