from __future__ import annotations

from pathlib import Path

from market_recorder.config import load_config
from market_recorder.contracts import build_market_event
from market_recorder.quality import build_data_quality_report
from market_recorder.storage import RawJsonlZstWriter, RawStreamRoute


def test_build_data_quality_report_flags_missing_routes(tmp_path: Path) -> None:
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

	config = load_config(config_path, repo_root=tmp_path)
	report = build_data_quality_report(config, stale_after_seconds=60)

	assert report.checked_route_count == 1
	assert report.missing_route_count == 1
	assert report.ok_route_count == 0
	assert report.routes[0].route == "pyth/sse/MULTI/price_stream"
	assert report.routes[0].status == "missing"


def test_build_data_quality_report_validates_existing_route(tmp_path: Path) -> None:
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

	config = load_config(config_path, repo_root=tmp_path)
	route = RawStreamRoute(source="pyth", transport="sse", source_symbol="MULTI", stream="price_stream")
	writer = RawJsonlZstWriter(
		data_root=config.runtime.data_root,
		route=route,
		run_id="quality-run",
		compression_level=config.storage.compression_level,
	)
	writer.write_record(
		build_market_event(
			source="pyth",
			transport="sse",
			stream="price_stream",
			stream_name=None,
			canonical_symbol="MULTI",
			source_symbol="MULTI",
			conn_id="quality-test",
			seq=1,
			payload={"price": 1},
		),
	)
	writer.close()

	report = build_data_quality_report(config, stale_after_seconds=60)

	assert report.checked_route_count == 1
	assert report.ok_route_count == 1
	assert report.missing_route_count == 0
	assert report.invalid_route_count == 0
	assert report.routes[0].status == "ok"
	assert report.routes[0].record_count == 1


def test_build_data_quality_report_marks_active_routes_as_incomplete(tmp_path: Path) -> None:
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

	config = load_config(config_path, repo_root=tmp_path)
	route = RawStreamRoute(source="pyth", transport="sse", source_symbol="MULTI", stream="price_stream")
	writer = RawJsonlZstWriter(
		data_root=config.runtime.data_root,
		route=route,
		run_id="quality-run",
		compression_level=config.storage.compression_level,
	)
	writer.write_record(
		build_market_event(
			source="pyth",
			transport="sse",
			stream="price_stream",
			stream_name=None,
			canonical_symbol="MULTI",
			source_symbol="MULTI",
			conn_id="quality-test",
			seq=1,
			payload={"price": 1},
		),
	)
	writer.flush()

	report = build_data_quality_report(config, stale_after_seconds=60)

	writer.close()

	assert report.checked_route_count == 1
	assert report.ok_route_count == 0
	assert report.missing_route_count == 0
	assert report.routes[0].status == "incomplete-active"
	assert report.routes[0].message is not None
	assert "sealed validation skipped" in report.routes[0].message


def test_build_data_quality_report_marks_tradingview_as_optional_when_idle(tmp_path: Path) -> None:
	sources_path = tmp_path / "sources.yaml"
	sources_path.write_text(
		"\n".join(
			[
				"pyth:",
				"  enabled: false",
				"  provider: hermes",
				"  http_base_url: https://hermes.pyth.network",
				"  feeds: []",
				"aster:",
				"  enabled: false",
				"  rest_base_url: https://fapi.asterdex.com",
				"  ws_base_url: wss://fstream.asterdex.com",
				"  symbols: []",
				"  streams: []",
				"tradingview:",
				"  enabled: true",
				"  webhook:",
				"    bind_host: 127.0.0.1",
				"    bind_port: 8000",
				"    path: /webhook/tradingview",
			],
		),
		encoding="utf-8",
	)

	config_path = tmp_path / "config.yaml"
	config_path.write_text(
		"\n".join(
			[
				"runtime:",
				"  environment: development",
				"  timezone: UTC",
				f"  data_root: {tmp_path / 'data'}",
				f"  sources_config: {sources_path}",
				"logging:",
				"  level: INFO",
				"  structured: false",
				"storage:",
				"  format: jsonl.zst",
				"  rotation: hourly",
				"  compression_level: 3",
				"validation:",
				"  enable_sample_checks: true",
			],
		),
		encoding="utf-8",
	)

	config = load_config(config_path, repo_root=tmp_path)
	report = build_data_quality_report(config, stale_after_seconds=60)

	assert report.checked_route_count == 1
	assert report.missing_route_count == 0
	assert report.ok_route_count == 0
	assert report.routes[0].status == "optional-missing"
	assert report.routes[0].required is False


def test_build_data_quality_report_matches_sanitized_aster_stream_paths(tmp_path: Path) -> None:
	sources_path = tmp_path / "sources.yaml"
	sources_path.write_text(
		"\n".join(
			[
				"pyth:",
				"  enabled: false",
				"  provider: hermes",
				"  http_base_url: https://hermes.pyth.network",
				"  feeds: []",
				"aster:",
				"  enabled: true",
				"  rest_base_url: https://fapi.asterdex.com",
				"  ws_base_url: wss://fstream.asterdex.com",
				"  depth:",
				"    snapshot_limit: 1000",
				"    snapshot_interval_seconds: 300",
				"  symbols:",
				"    - canonical_symbol: BTCUSD",
				"      source_symbol: BTCUSDT",
				"  streams:",
				"    - depth@100ms",
				"tradingview:",
				"  enabled: false",
				"  webhook:",
				"    bind_host: 127.0.0.1",
				"    bind_port: 8000",
				"    path: /webhook/tradingview",
			],
		),
		encoding="utf-8",
	)

	config_path = tmp_path / "config.yaml"
	config_path.write_text(
		"\n".join(
			[
				"runtime:",
				"  environment: development",
				"  timezone: UTC",
				f"  data_root: {tmp_path / 'data'}",
				f"  sources_config: {sources_path}",
				"logging:",
				"  level: INFO",
				"  structured: false",
				"storage:",
				"  format: jsonl.zst",
				"  rotation: hourly",
				"  compression_level: 3",
				"validation:",
				"  enable_sample_checks: true",
			],
		),
		encoding="utf-8",
	)

	config = load_config(config_path, repo_root=tmp_path)
	route = RawStreamRoute(source="aster", transport="ws", source_symbol="BTCUSDT", stream="depth@100ms")
	writer = RawJsonlZstWriter(
		data_root=config.runtime.data_root,
		route=route,
		run_id="quality-run",
		compression_level=config.storage.compression_level,
	)
	writer.write_record(
		build_market_event(
			source="aster",
			transport="ws",
			stream="depth@100ms",
			stream_name="btcusdt@depth@100ms",
			canonical_symbol="BTCUSD",
			source_symbol="BTCUSDT",
			conn_id="quality-test",
			seq=1,
			payload={"data": {"U": 1, "u": 1, "pu": 1, "b": [], "a": []}},
		),
	)
	writer.close()

	report = build_data_quality_report(config, stale_after_seconds=60)

	assert report.checked_route_count == 2
	assert report.ok_route_count == 1
	assert any(route.route == "aster/ws/BTCUSDT/depth_100ms" and route.status == "ok" for route in report.routes)