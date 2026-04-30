"""Pyth Hermes SSE capture helpers."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from urllib.parse import quote

import aiohttp

from ..contracts import build_market_event, build_recorder_error
from ..runtime import RecorderRuntime
from ..storage import RawJsonlZstWriter, RawStreamRoute, is_sealed_raw_file

_PYTH_ROUTE = RawStreamRoute(
    source="pyth",
    transport="sse",
    source_symbol="MULTI",
    stream="price_stream",
)
_PYTH_ERROR_ROUTE = RawStreamRoute(
    source="pyth",
    transport="sse",
    source_symbol="MULTI",
    stream="recorder_error",
)
_DEFAULT_RECONNECT_DELAY_SECONDS = 1.0


@dataclass(frozen=True, slots=True)
class PythCaptureSummary:
    records_written: int
    reconnect_count: int
    error_record_count: int
    output_paths: tuple[Path, ...]


def build_pyth_stream_url(base_url: str, feed_ids: Sequence[str]) -> str:
    normalized_base = base_url.rstrip("/")
    query = "&".join(f"ids[]={quote(feed_id, safe='')}" for feed_id in feed_ids)
    return f"{normalized_base}/v2/updates/price/stream?{query}"


async def iter_sse_payloads(stream) -> AsyncIterator[str]:
    pending_data: list[str] = []
    while True:
        raw_line = await stream.readline()
        if raw_line == b"":
            break

        line = raw_line.decode("utf-8").rstrip("\r\n")
        if not line:
            if pending_data:
                yield "\n".join(pending_data)
                pending_data.clear()
            continue
        if line.startswith(":"):
            continue
        if line.startswith("data:"):
            pending_data.append(line[5:].lstrip())

    if pending_data:
        yield "\n".join(pending_data)


async def capture_pyth(
    *,
    runtime: RecorderRuntime,
    event_limit: int | None = None,
    duration_seconds: float | None = None,
) -> PythCaptureSummary:
    config = runtime.config
    feed_ids = [feed.feed_id for feed in config.sources.pyth.feeds]
    stream_url = build_pyth_stream_url(config.sources.pyth.http_base_url, feed_ids)
    writer = RawJsonlZstWriter(
        data_root=config.runtime.data_root,
        route=_PYTH_ROUTE,
        run_id=runtime.run_id,
        compression_level=config.storage.compression_level,
        rotation_policy=config.storage.resolve_rotation_policy(
            source=_PYTH_ROUTE.source,
            stream=_PYTH_ROUTE.stream,
        ),
    )
    error_writer = RawJsonlZstWriter(
        data_root=config.runtime.data_root,
        route=_PYTH_ERROR_ROUTE,
        run_id=runtime.run_id,
        compression_level=config.storage.compression_level,
        rotation_policy=config.storage.resolve_rotation_policy(
            source=_PYTH_ERROR_ROUTE.source,
            stream=_PYTH_ERROR_ROUTE.stream,
        ),
    )
    deadline = monotonic() + duration_seconds if duration_seconds is not None else None
    records_written = 0
    reconnect_count = 0
    error_record_count = 0
    connection_number = 0
    output_paths: set[Path] = set()

    try:
        while not _stop_requested(
            records_written=records_written,
            event_limit=event_limit,
            deadline=deadline,
        ):
            connection_number += 1
            conn_id = f"{runtime.run_id}-pyth-{connection_number:03d}"
            try:
                async with runtime.session.get(
                    stream_url,
                    headers={"Accept": "text/event-stream"},
                    timeout=aiohttp.ClientTimeout(total=None, connect=10, sock_read=None),
                ) as response:
                    response.raise_for_status()
                    ended_cleanly = True
                    async for payload_text in iter_sse_payloads(response.content):
                        try:
                            payload = json.loads(payload_text)
                        except json.JSONDecodeError as exc:
                            error_record_count += 1
                            _add_output_path_if_sealed(
                                output_paths,
                                error_writer.write_record(
                                    build_recorder_error(
                                        source="pyth",
                                        transport="sse",
                                        stream="recorder_error",
                                        stream_name=None,
                                        canonical_symbol="MULTI",
                                        source_symbol="MULTI",
                                        conn_id=conn_id,
                                        seq=error_record_count,
                                        payload={
                                            "kind": "json_decode_error",
                                            "message": str(exc),
                                            "raw": payload_text,
                                        },
                                    ),
                                ),
                            )
                            continue

                        records_written += 1
                        _add_output_path_if_sealed(
                            output_paths,
                            writer.write_record(
                                build_market_event(
                                    source="pyth",
                                    transport="sse",
                                    stream="price_stream",
                                    stream_name=None,
                                    canonical_symbol="MULTI",
                                    source_symbol="MULTI",
                                    conn_id=conn_id,
                                    seq=records_written,
                                    payload=payload,
                                ),
                            ),
                        )
                        if _stop_requested(
                            records_written=records_written,
                            event_limit=event_limit,
                            deadline=deadline,
                        ):
                            ended_cleanly = False
                            break

                    writer.flush()
                    error_writer.flush()
                    if _stop_requested(
                        records_written=records_written,
                        event_limit=event_limit,
                        deadline=deadline,
                    ):
                        break
                    if ended_cleanly:
                        reconnect_count += 1
                        await asyncio.sleep(_DEFAULT_RECONNECT_DELAY_SECONDS)
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                reconnect_count += 1
                error_record_count += 1
                _add_output_path_if_sealed(
                    output_paths,
                    error_writer.write_record(
                        build_recorder_error(
                            source="pyth",
                            transport="sse",
                            stream="recorder_error",
                            stream_name=None,
                            canonical_symbol="MULTI",
                            source_symbol="MULTI",
                            conn_id=conn_id,
                            seq=error_record_count,
                            payload={
                                "kind": exc.__class__.__name__,
                                "message": str(exc),
                                "url": stream_url,
                            },
                        ),
                    ),
                )
                error_writer.flush()
                if _stop_requested(
                    records_written=records_written,
                    event_limit=event_limit,
                    deadline=deadline,
                ):
                    break
                await asyncio.sleep(_DEFAULT_RECONNECT_DELAY_SECONDS)
    finally:
        writer.close()
        error_writer.close()
        output_paths.update(_collect_sealed_output_paths(writer, error_writer))

    return PythCaptureSummary(
        records_written=records_written,
        reconnect_count=reconnect_count,
        error_record_count=error_record_count,
        output_paths=tuple(sorted(output_paths)),
    )


def _stop_requested(*, records_written: int, event_limit: int | None, deadline: float | None) -> bool:
    if event_limit is not None and records_written >= event_limit:
        return True
    if deadline is not None and monotonic() >= deadline:
        return True
    return False


def _add_output_path_if_sealed(output_paths: set[Path], path: Path) -> None:
    if is_sealed_raw_file(path):
        output_paths.add(path)


def _collect_sealed_output_paths(*writers: RawJsonlZstWriter) -> set[Path]:
    sealed_paths: set[Path] = set()
    for writer in writers:
        for segment in writer.sealed_segments:
            sealed_paths.add(segment.sealed_path)
    return sealed_paths