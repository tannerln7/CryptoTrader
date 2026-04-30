from __future__ import annotations

from pathlib import Path

import pytest

from market_recorder.config import (
  CHECKOUT_LAYOUT,
  DEFAULT_CONFIG_PATH,
  DEFAULT_INSTALLED_CONFIG_ROOT,
  DEFAULT_INSTALLED_INSTANCE,
  DEFAULT_SOURCES_PATH,
  ConfigError,
  default_config_path,
  default_instance_name,
  load_config,
)


def test_load_config_reads_example_files(monkeypatch) -> None:
    monkeypatch.setenv("MARKET_RECORDER_LAYOUT", CHECKOUT_LAYOUT)
    config = load_config()

    assert config.config_path == (config.repo_root / DEFAULT_CONFIG_PATH).resolve()
    assert config.sources_path == (config.repo_root / DEFAULT_SOURCES_PATH).resolve()
    assert config.runtime.timezone == "UTC"
    assert config.storage.format == "jsonl.zst"
    assert config.storage.compression_level == 3
    assert config.sources.aster.depth.snapshot_limit == 1000
    assert config.sources.aster.depth.snapshot_interval_seconds == 300
    assert config.enabled_sources == ("pyth", "aster")


def test_load_config_infers_repo_root_from_absolute_config_path(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MARKET_RECORDER_LAYOUT", CHECKOUT_LAYOUT)
    (tmp_path / "pyproject.toml").write_text("[build-system]\nrequires = []\n", encoding="utf-8")
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "config.example.yaml").write_text("runtime: {}\n", encoding="utf-8")
    sources_path = config_dir / "sources.example.yaml"
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

    instance_config_dir = tmp_path / "data" / "systemd" / "main"
    instance_config_dir.mkdir(parents=True)
    config_path = instance_config_dir / "config.yaml"
    config_path.write_text(
        """
runtime:
  environment: development
  timezone: UTC
  data_root: ./data
  sources_config: config/sources.example.yaml
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

    monkeypatch.chdir(tmp_path / "data")

    config = load_config(config_path)

    assert config.repo_root == tmp_path.resolve()
    assert config.config_path == config_path.resolve()
    assert config.sources_path == sources_path.resolve()


def test_default_config_path_uses_installed_production_instance(monkeypatch) -> None:
    monkeypatch.delenv("MARKET_RECORDER_LAYOUT", raising=False)
    monkeypatch.delenv("MARKET_RECORDER_INSTANCE", raising=False)

    assert default_instance_name() == DEFAULT_INSTALLED_INSTANCE
    assert default_config_path() == (DEFAULT_INSTALLED_CONFIG_ROOT / "production.yaml").resolve()


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


def test_load_config_reads_structured_rotation_policies(tmp_path: Path) -> None:
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
  enabled: true
  rest_base_url: https://fapi.asterdex.com
  ws_base_url: wss://fstream.asterdex.com
  depth:
    snapshot_limit: 1000
    snapshot_interval_seconds: 300
  symbols:
    - canonical_symbol: BTCUSD
      source_symbol: BTCUSDT
  streams:
    - bookTicker
    - depth@100ms
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
  data_root: ./data
  sources_config: {sources_path}
logging:
  level: INFO
  structured: false
storage:
  format: jsonl.zst
  rotation:
    default:
      max_age_seconds: 3600
    classes:
      high_frequency:
        max_age_seconds: 3600
        max_bytes: 536870912
      low_frequency:
        max_age_seconds: 86400
        max_bytes: 134217728
    stream_classes:
      aster:
        bookTicker: high_frequency
        depth_100ms: high_frequency
      tradingview:
        alert: low_frequency
    manual_rotation:
      enabled: true
      require_reason: true
      min_age_seconds: 300
      min_bytes: 1048576
      cooldown_seconds: 300
  compression_level: 3
validation:
  enable_sample_checks: true
""".strip(),
		encoding="utf-8",
	)

	config = load_config(config_path, repo_root=tmp_path)

	assert config.storage.rotation.uses_legacy_hourly is False
	assert config.storage.resolve_rotation_policy(source="aster", stream="bookTicker").max_bytes == 536870912
	assert config.storage.resolve_rotation_policy(source="aster", stream="depth@100ms").max_bytes == 536870912
	assert config.storage.resolve_rotation_policy(source="pyth", stream="price_stream").max_age_seconds == 3600
	assert config.storage.rotation.manual_rotation.enabled is True
	assert config.storage.rotation.manual_rotation.min_bytes == 1048576


def test_load_config_rejects_unknown_rotation_classes(tmp_path: Path) -> None:
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
  timezone: UTC
  data_root: ./data
  sources_config: {sources_path}
logging:
  level: INFO
  structured: false
storage:
  format: jsonl.zst
  rotation:
    default:
      max_age_seconds: 3600
    classes:
      low_frequency:
        max_age_seconds: 86400
    stream_classes:
      aster:
        bookTicker: high_frequency
  compression_level: 3
validation:
  enable_sample_checks: true
""".strip(),
		encoding="utf-8",
	)

	with pytest.raises(ConfigError, match="undefined rotation class"):
		load_config(config_path, repo_root=tmp_path)


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