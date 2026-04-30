from __future__ import annotations

from market_recorder.timeutil import make_run_id, sample_clock


def test_sample_clock_captures_utc_and_monotonic_fields() -> None:
    sample = sample_clock()

    assert sample.ts_recv_ns > 0
    assert sample.monotonic_ns > 0
    assert sample.ts_recv_utc.endswith("Z")


def test_make_run_id_uses_prefix_and_utc_timestamp_shape() -> None:
    run_id = make_run_id("recorder")

    assert run_id.startswith("recorder-")
    assert len(run_id.split("-")) == 3