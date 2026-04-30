from __future__ import annotations

import asyncio
import json
from pathlib import Path

from market_recorder.config import load_config
from market_recorder.service import default_health_manifest_path, run_recorder_service


def test_run_recorder_service_writes_health_manifest(tmp_path: Path, monkeypatch) -> None:
	async def fake_capture_pyth(*, runtime, duration_seconds=None):
		assert runtime.run_id.startswith("recorder-")
		return {"kind": "pyth", "duration_seconds": duration_seconds}

	monkeypatch.setattr("market_recorder.service.capture_pyth", fake_capture_pyth)

	sources_path = tmp_path / "sources.yaml"
	sources_path.write_text(
		"""
pyth:
  enabled: true
  provider: hermes
  http_base_url: https://hermes.pyth.network
  feeds:
    - canonical_symbol: BTCUSD
      source_symbol: BTC/USD
      feed_id: 0xe62df6c8b4a85fe1a67db44dc12de5db330f7ac66b72dc658afedf0f4a415b43
aster:
  enabled: false
  rest_base_url: https://fapi.asterdex.com
  ws_base_url: wss://fstream.asterdex.com
  symbols: []
  streams: []
tradingview:
  enabled: false
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

	async def scenario() -> None:
		from market_recorder.runtime import RecorderRuntime

		runtime = RecorderRuntime.from_config(load_config(config_path, repo_root=tmp_path))
		try:
			summary = await run_recorder_service(
				runtime=runtime,
				duration_seconds=0.01,
				health_interval_seconds=0.01,
			)
			assert summary.component_statuses == {"pyth": "completed"}
			health_path = default_health_manifest_path(runtime.config.runtime.data_root, runtime.run_id)
			assert health_path.exists()
			payload = json.loads(health_path.read_text(encoding="utf-8"))
			assert payload["component_statuses"]["pyth"] == "completed"
			assert payload["run_id"] == runtime.run_id
		finally:
			await runtime.close()

	asyncio.run(scenario())