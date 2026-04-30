from __future__ import annotations

import asyncio

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