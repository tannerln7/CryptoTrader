from __future__ import annotations

import asyncio

import aiohttp
from aiohttp import web

from market_recorder.config import load_config
from market_recorder.runtime import RecorderRuntime


def test_runtime_initializes_and_cleans_up_managed_session() -> None:
    async def scenario() -> None:
        runtime = RecorderRuntime.from_config(load_config())
        await runtime.start()

        session = runtime.session
        assert runtime.run_id.startswith("recorder-")
        assert runtime.background_tasks == set()
        assert session.closed is False

        await runtime.close()
        assert session.closed is True

    asyncio.run(scenario())


def test_runtime_can_bind_and_serve_a_tcp_site() -> None:
    async def handler(_request: web.Request) -> web.Response:
        return web.Response(text="ok")

    async def scenario() -> None:
        runtime = RecorderRuntime.from_config(load_config())
        runtime.app.router.add_get("/health", handler)

        site = await runtime.start_site("127.0.0.1", 0)
        sockets = getattr(site, "_server").sockets
        port = sockets[0].getsockname()[1]

        async with aiohttp.ClientSession() as session:
            async with session.get(f"http://127.0.0.1:{port}/health") as response:
                assert response.status == 200
                assert await response.text() == "ok"

        await runtime.close()

    asyncio.run(scenario())