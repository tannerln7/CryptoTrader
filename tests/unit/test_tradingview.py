from __future__ import annotations

import asyncio

import aiohttp

from market_recorder.alerts import TradingViewWebhookService, parse_tradingview_body
from market_recorder.config import load_config
from market_recorder.runtime import RecorderRuntime
from market_recorder.storage import iter_raw_records, validate_raw_file


def test_parse_tradingview_body_preserves_plain_text() -> None:
	body, body_format = parse_tradingview_body("text/plain", "hello")

	assert body == "hello"
	assert body_format == "text"


def test_tradingview_webhook_service_records_json_requests(tmp_path) -> None:
	async def scenario() -> None:
		sources_path = tmp_path / "sources.yaml"
		sources_path.write_text(
			"""
pyth:
  enabled: false
  provider: hermes
  http_base_url: https://hermes.pyth.network
  feeds: []
aster:
  enabled: false
  rest_base_url: https://fapi.asterdex.com
  ws_base_url: wss://fstream.asterdex.com
  symbols: []
  streams: []
tradingview:
  enabled: true
  webhook:
    bind_host: 127.0.0.1
    bind_port: 8000
    path: /webhook/tradingview
""".strip(),
			encoding="utf-8",
		)

		config_path = tmp_path / "config.yaml"
		config_path.write_text(
			f"""
runtime:
  environment: development
  timezone: UTC
  data_root: {tmp_path / 'data'}
  sources_config: {sources_path}
logging:
  level: INFO
  structured: false
storage:
  format: jsonl.zst
  rotation: hourly
  compression_level: 3
validation:
  enable_sample_checks: true
""".strip(),
			encoding="utf-8",
		)

		runtime = RecorderRuntime.from_config(load_config(config_path, repo_root=tmp_path))
		service = TradingViewWebhookService.from_runtime(
			runtime,
			bind_host="127.0.0.1",
			bind_port=0,
			path="/webhook/test",
			request_limit=1,
		)
		await service.start()

		async with aiohttp.ClientSession() as session:
			async with session.post(
				f"{service.base_url}/webhook/test",
				json={"event": "swing_choch", "symbol": "BTCUSD"},
			) as response:
				assert response.status == 200
				assert await response.text() == "ok"

		await service.wait(duration_seconds=1)
		summary = service.build_summary()
		assert summary.request_count == 1
		assert summary.error_record_count == 0
		assert len(summary.output_paths) == 1

		record_path = summary.output_paths[0]
		validation = validate_raw_file(record_path)
		assert validation.record_count == 1

		record = next(iter_raw_records(record_path))
		assert record["schema"] == "raw.alert_event.v1"
		assert record["transport"] == "webhook"
		assert record["payload"]["body_format"] == "json"
		assert record["payload"]["body"]["event"] == "swing_choch"

		await service.close()
		await runtime.close()

	asyncio.run(scenario())