"""Recorder runtime lifecycle built around aiohttp cleanup contexts."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any

import aiohttp
from aiohttp import web

from .config import RecorderConfig
from .timeutil import make_run_id

RECORDER_CONFIG = web.AppKey("recorder_config", RecorderConfig)
RUN_ID = web.AppKey("run_id", str)
HTTP_SESSION = web.AppKey("http_session", aiohttp.ClientSession)
BACKGROUND_TASKS = web.AppKey("background_tasks", set[asyncio.Task[Any]])


def build_runtime_application(config: RecorderConfig) -> web.Application:
    """Create the Phase 1 runtime container without binding any external endpoints."""
    app = web.Application()
    app[RECORDER_CONFIG] = config
    app[RUN_ID] = make_run_id("recorder")
    app.cleanup_ctx.append(_client_session_ctx)
    app.cleanup_ctx.append(_background_task_registry_ctx)
    return app


@dataclass(slots=True)
class RecorderRuntime:
    config: RecorderConfig
    app: web.Application
    _runner: web.AppRunner | None = None
    _sites: list[web.BaseSite] = field(default_factory=list)

    @classmethod
    def from_config(cls, config: RecorderConfig) -> "RecorderRuntime":
        return cls(config=config, app=build_runtime_application(config))

    @property
    def run_id(self) -> str:
        return self.app[RUN_ID]


    @property
    def session(self) -> aiohttp.ClientSession:
        return self.app[HTTP_SESSION]


    @property
    def background_tasks(self) -> set[asyncio.Task[Any]]:
        return self.app[BACKGROUND_TASKS]


    async def start(self) -> None:
        if self._runner is not None:
            return
        runner = web.AppRunner(self.app, handle_signals=False)
        await runner.setup()
        self._runner = runner


    async def start_site(self, host: str, port: int) -> web.TCPSite:
        await self.start()
        if self._runner is None:
            raise RuntimeError("Recorder runtime runner was not initialized")

        site = web.TCPSite(self._runner, host, port)
        await site.start()
        self._sites.append(site)
        return site


    async def close(self) -> None:
        if self._runner is None:
            return
        await self._runner.cleanup()
        self._runner = None
        self._sites.clear()


    async def __aenter__(self) -> "RecorderRuntime":
        await self.start()
        return self


    async def __aexit__(self, exc_type, exc, traceback) -> None:
        await self.close()


async def _client_session_ctx(app: web.Application) -> AsyncIterator[None]:
    timeout = aiohttp.ClientTimeout(total=30, connect=5, sock_read=30)
    connector = aiohttp.TCPConnector(limit=32, limit_per_host=16, ttl_dns_cache=300)
    app[HTTP_SESSION] = aiohttp.ClientSession(
        timeout=timeout,
        connector=connector,
        raise_for_status=False,
    )
    yield
    await app[HTTP_SESSION].close()


async def _background_task_registry_ctx(app: web.Application) -> AsyncIterator[None]:
    app[BACKGROUND_TASKS] = set()
    yield
    tasks = tuple(app[BACKGROUND_TASKS])
    for task in tasks:
        task.cancel()
    for task in tasks:
        with suppress(asyncio.CancelledError):
            await task