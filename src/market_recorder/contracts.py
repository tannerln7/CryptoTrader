"""Shared raw-envelope helpers for recorder sources."""

from __future__ import annotations

from typing import Any, Literal, TypedDict

from .timeutil import sample_clock

RawSchemaName = Literal[
    "raw.market_event.v1",
    "raw.rest_snapshot.v1",
    "raw.alert_event.v1",
    "raw.recorder_error.v1",
    "raw.sse_line.v1",
]


class RawEnvelope(TypedDict):
    schema: str
    source: str
    transport: str
    stream: str
    stream_name: str | None
    canonical_symbol: str
    source_symbol: str
    ts_recv_ns: int
    ts_recv_utc: str
    monotonic_ns: int
    conn_id: str
    seq: int
    payload: Any


def build_raw_envelope(
    *,
    schema: RawSchemaName,
    source: str,
    transport: str,
    stream: str,
    canonical_symbol: str,
    source_symbol: str,
    conn_id: str,
    seq: int,
    payload: Any,
    stream_name: str | None = None,
    ts_recv_ns: int | None = None,
    ts_recv_utc: str | None = None,
    monotonic_value: int | None = None,
) -> RawEnvelope:
    """Build a raw recorder envelope aligned with the schema reference."""

    clock = sample_clock()
    return RawEnvelope(
        schema=schema,
        source=source,
        transport=transport,
        stream=stream,
        stream_name=stream_name,
        canonical_symbol=canonical_symbol,
        source_symbol=source_symbol,
        ts_recv_ns=clock.ts_recv_ns if ts_recv_ns is None else ts_recv_ns,
        ts_recv_utc=clock.ts_recv_utc if ts_recv_utc is None else ts_recv_utc,
        monotonic_ns=clock.monotonic_ns if monotonic_value is None else monotonic_value,
        conn_id=conn_id,
        seq=seq,
        payload=payload,
    )


def build_market_event(**kwargs: Any) -> RawEnvelope:
    return build_raw_envelope(schema="raw.market_event.v1", **kwargs)


def build_rest_snapshot(**kwargs: Any) -> RawEnvelope:
    return build_raw_envelope(schema="raw.rest_snapshot.v1", **kwargs)


def build_alert_event(**kwargs: Any) -> RawEnvelope:
    return build_raw_envelope(schema="raw.alert_event.v1", **kwargs)


def build_recorder_error(**kwargs: Any) -> RawEnvelope:
    return build_raw_envelope(schema="raw.recorder_error.v1", **kwargs)