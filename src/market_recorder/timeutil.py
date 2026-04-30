"""UTC and monotonic clock helpers for recorder events."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from time import monotonic_ns as monotonic_clock_ns
from time import time_ns
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class ClockSample:
    ts_recv_ns: int
    ts_recv_utc: str
    monotonic_ns: int


def utc_now() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    """Return the current UTC time in ISO-8601 form ending with Z."""
    return utc_now().isoformat().replace("+00:00", "Z")


def utc_now_ns() -> int:
    """Return the current wall-clock UTC timestamp in nanoseconds."""
    return time_ns()


def monotonic_ns() -> int:
    """Return the current process monotonic timestamp in nanoseconds."""
    return monotonic_clock_ns()


def sample_clock() -> ClockSample:
    """Capture wall-clock and monotonic timestamps together."""
    timestamp_ns = utc_now_ns()
    timestamp_utc = datetime.fromtimestamp(timestamp_ns / 1_000_000_000, tz=timezone.utc)
    return ClockSample(
        ts_recv_ns=timestamp_ns,
        ts_recv_utc=timestamp_utc.isoformat().replace("+00:00", "Z"),
        monotonic_ns=monotonic_ns(),
    )


def make_run_id(prefix: str) -> str:
    """Create a compact UTC-prefixed run identifier."""
    return f"{prefix}-{utc_now().strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}"