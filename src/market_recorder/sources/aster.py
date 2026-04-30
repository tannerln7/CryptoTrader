"""Aster non-depth market stream capture helpers."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from time import monotonic

import aiohttp

from ..config import AsterSourceConfig
from ..contracts import build_market_event, build_recorder_error
from ..runtime import RecorderRuntime
from ..storage import RawJsonlZstWriter, RawStreamRoute, is_sealed_raw_file

_ASTER_ERROR_ROUTE = RawStreamRoute(
    source="aster",
    transport="ws",
    source_symbol="MULTI",
    stream="recorder_error",
)
_DEFAULT_RECONNECT_DELAY_SECONDS = 1.0


@dataclass(frozen=True, slots=True)
class AsterStreamTarget:
    canonical_symbol: str
    source_symbol: str
    logical_stream: str
    stream_name: str


@dataclass(frozen=True, slots=True)
class AsterCaptureSummary:
    records_written: int
    reconnect_count: int
    error_record_count: int
    output_paths: tuple[Path, ...]


def build_aster_stream_targets(config: AsterSourceConfig) -> tuple[AsterStreamTarget, ...]:
    targets: list[AsterStreamTarget] = []
    for symbol in config.symbols:
        for logical_stream in config.streams:
            if _is_depth_stream(logical_stream):
                continue
            targets.append(
                AsterStreamTarget(
                    canonical_symbol=symbol.canonical_symbol,
                    source_symbol=symbol.source_symbol,
                    logical_stream=logical_stream,
                    stream_name=f"{symbol.source_symbol.lower()}@{logical_stream}",
                ),
            )
    return tuple(targets)


def build_aster_combined_stream_url(base_url: str, targets: tuple[AsterStreamTarget, ...]) -> str:
    normalized_base = base_url.rstrip("/")
    stream_path = "/".join(target.stream_name for target in targets)
    return f"{normalized_base}/stream?streams={stream_path}"


async def capture_aster(
    *,
    runtime: RecorderRuntime,
    event_limit: int | None = None,
    duration_seconds: float | None = None,
) -> AsterCaptureSummary:
    config = runtime.config
    targets = build_aster_stream_targets(config.sources.aster)
    target_map = {target.stream_name: target for target in targets}
    combined_url = build_aster_combined_stream_url(config.sources.aster.ws_base_url, targets)
    writers = {
        target.stream_name: RawJsonlZstWriter(
            data_root=config.runtime.data_root,
            route=RawStreamRoute(
                source="aster",
                transport="ws",
                source_symbol=target.source_symbol,
                stream=target.logical_stream,
            ),
            run_id=runtime.run_id,
            compression_level=config.storage.compression_level,
            rotation_policy=config.storage.resolve_rotation_policy(
                source="aster",
                stream=target.logical_stream,
            ),
        )
        for target in targets
    }
    error_writer = RawJsonlZstWriter(
        data_root=config.runtime.data_root,
        route=_ASTER_ERROR_ROUTE,
        run_id=runtime.run_id,
        compression_level=config.storage.compression_level,
        rotation_policy=config.storage.resolve_rotation_policy(
            source=_ASTER_ERROR_ROUTE.source,
            stream=_ASTER_ERROR_ROUTE.stream,
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
            conn_id = f"{runtime.run_id}-aster-{connection_number:03d}"
            try:
                async with runtime.session.ws_connect(combined_url, heartbeat=None, autoclose=True, autoping=True) as ws:
                    async for message in ws:
                        if message.type == aiohttp.WSMsgType.TEXT:
                            payload = json.loads(message.data)
                            if not isinstance(payload, dict):
                                raise ValueError("Aster wrapper message was not a JSON object")
                            stream_name = payload.get("stream")
                            if not isinstance(stream_name, str):
                                raise ValueError("Aster wrapper message missing stream name")
                            target = target_map.get(stream_name)
                            if target is None:
                                raise ValueError(f"Unexpected Aster stream name: {stream_name}")
                            records_written += 1
                            _add_output_path_if_sealed(
                                output_paths,
                                writers[stream_name].write_record(
                                    build_market_event(
                                        source="aster",
                                        transport="ws",
                                        stream=target.logical_stream,
                                        stream_name=stream_name,
                                        canonical_symbol=target.canonical_symbol,
                                        source_symbol=target.source_symbol,
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
                                break
                        elif message.type in {aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSE}:
                            break
                        elif message.type == aiohttp.WSMsgType.ERROR:
                            raise aiohttp.ClientError(str(ws.exception()))

                    _flush_all_writers(writers, error_writer)
                    if _stop_requested(
                        records_written=records_written,
                        event_limit=event_limit,
                        deadline=deadline,
                    ):
                        break
                    reconnect_count += 1
                    await asyncio.sleep(_DEFAULT_RECONNECT_DELAY_SECONDS)
            except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, json.JSONDecodeError) as exc:
                reconnect_count += 1
                error_record_count += 1
                _add_output_path_if_sealed(
                    output_paths,
                    error_writer.write_record(
                        build_recorder_error(
                            source="aster",
                            transport="ws",
                            stream="recorder_error",
                            stream_name=None,
                            canonical_symbol="MULTI",
                            source_symbol="MULTI",
                            conn_id=conn_id,
                            seq=error_record_count,
                            payload={
                                "kind": exc.__class__.__name__,
                                "message": str(exc),
                                "url": combined_url,
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
        _close_all_writers(writers, error_writer)
        output_paths.update(_collect_sealed_output_paths(*writers.values(), error_writer))

    return AsterCaptureSummary(
        records_written=records_written,
        reconnect_count=reconnect_count,
        error_record_count=error_record_count,
        output_paths=tuple(sorted(output_paths)),
    )


def _is_depth_stream(logical_stream: str) -> bool:
    stream_name = logical_stream.lower()
    return stream_name.startswith("depth") or "depth" in stream_name


def _flush_all_writers(
    writers: dict[str, RawJsonlZstWriter],
    error_writer: RawJsonlZstWriter,
) -> None:
    for writer in writers.values():
        writer.flush()
    error_writer.flush()


def _close_all_writers(
    writers: dict[str, RawJsonlZstWriter],
    error_writer: RawJsonlZstWriter,
) -> None:
    for writer in writers.values():
        writer.close()
    error_writer.close()


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