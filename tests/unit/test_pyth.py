from __future__ import annotations

import asyncio

from market_recorder.sources.pyth import build_pyth_stream_url, iter_sse_payloads


class FakeSseStream:
    def __init__(self, lines: list[bytes]) -> None:
        self._lines = lines
        self._index = 0

    async def readline(self) -> bytes:
        if self._index >= len(self._lines):
            return b""
        line = self._lines[self._index]
        self._index += 1
        return line


def test_build_pyth_stream_url_encodes_feed_ids() -> None:
    url = build_pyth_stream_url(
        "https://hermes.pyth.network",
        [
            "0xe62df6c8b4a85fe1a67db44dc12de5db330f7ac66b72dc658afedf0f4a415b43",
            "0xff61491a931112ddf1bd8147cd1b641375f79f5825126d665480874634fd0ace",
        ],
    )

    assert url.startswith("https://hermes.pyth.network/v2/updates/price/stream?")
    assert "ids[]=0xe62df6c8b4a85fe1a67db44dc12de5db330f7ac66b72dc658afedf0f4a415b43" in url
    assert "ids[]=0xff61491a931112ddf1bd8147cd1b641375f79f5825126d665480874634fd0ace" in url


def test_iter_sse_payloads_yields_joined_data_events() -> None:
    async def scenario() -> list[str]:
        payloads: list[str] = []
        stream = FakeSseStream(
            [
                b": keepalive\n",
                b"data: {\"id\":\"btc\"\n",
                b"data: ,\"value\":1}\n",
                b"\n",
                b"data: {\"id\":\"eth\",\"value\":2}\n",
                b"\n",
            ],
        )
        async for payload in iter_sse_payloads(stream):
            payloads.append(payload)
        return payloads

    assert asyncio.run(scenario()) == [
        '{"id":"btc"\n,"value":1}',
        '{"id":"eth","value":2}',
    ]