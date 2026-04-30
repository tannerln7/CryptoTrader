from __future__ import annotations

from pathlib import Path

import pytest

from market_recorder.config import (
  DEFAULT_CONFIG_PATH,
  DEFAULT_SOURCES_PATH,
  ConfigError,
  load_config,
)


def test_load_config_reads_example_files() -> None:
    config = load_config()

    assert config.config_path == DEFAULT_CONFIG_PATH
    assert config.sources_path == DEFAULT_SOURCES_PATH
    assert config.runtime.timezone == "UTC"
    assert config.storage.format == "jsonl.zst"
    assert config.storage.compression_level == 3
    assert config.sources.aster.depth.snapshot_limit == 1000
    assert config.sources.aster.depth.snapshot_interval_seconds == 300
    assert config.enabled_sources == ("pyth", "aster")


def test_load_config_defaults_aster_depth_settings_when_missing(tmp_path: Path) -> None:
    sources_path = tmp_path / "sources.yaml"
    sources_path.write_text(
        """
pyth:
  enabled: false
  provider: hermes
  http_base_url: https://hermes.pyth.network
  feeds: []
aster:
  enabled: true
  rest_base_url: https://fapi.asterdex.com
  ws_base_url: wss://fstream.asterdex.com
  symbols:
    - canonical_symbol: BTCUSD
      source_symbol: BTCUSDT
  streams:
    - depth@100ms
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
  data_root: ./data
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

    config = load_config(config_path, repo_root=tmp_path)

    assert config.sources.aster.depth.snapshot_limit == 1000
    assert config.sources.aster.depth.snapshot_interval_seconds == 300


def test_load_config_rejects_non_utc_timezone(tmp_path: Path) -> None:
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
  timezone: US/Eastern
  data_root: ./data
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

    with pytest.raises(ConfigError, match="runtime.timezone must be UTC"):
        load_config(config_path, repo_root=tmp_path)