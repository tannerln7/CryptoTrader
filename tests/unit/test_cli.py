from __future__ import annotations

from pathlib import Path

from market_recorder.alerts import TradingViewWebhookSummary
from market_recorder.cli import build_parser, main
from market_recorder.contracts import build_market_event
from market_recorder.service_control import (
    RecorderServiceStatus,
    default_socket_path,
)
from market_recorder.storage import RawJsonlZstWriter, RawStreamRoute, validate_raw_file


def _service_status(
    instance: str,
    *,
    state: str,
    pid: int | None = None,
    run_id: str | None = None,
    config_path: Path | None = None,
    sources_path: Path | None = None,
    data_root: Path | None = None,
    health_path: Path | None = None,
    started_at_utc: str | None = None,
    updated_at_utc: str | None = None,
    finished_at_utc: str | None = None,
    message: str | None = None,
) -> RecorderServiceStatus:
    return RecorderServiceStatus(
        status=state,
        instance=instance,
        unit_name=f"market-recorder@{instance}.service",
        socket_path=default_socket_path(instance),
        pid=pid,
        run_id=run_id,
        config_path=config_path,
        sources_path=sources_path,
        data_root=data_root,
        health_path=health_path,
        started_at_utc=started_at_utc,
        updated_at_utc=updated_at_utc,
        finished_at_utc=finished_at_utc,
        message=message,
        available_via_socket=state in {"running", "starting", "stopping"},
    )


def test_cli_validate_config_reports_loaded_paths(capsys) -> None:
    exit_code = main(["validate-config"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Configuration valid:" in captured.out
    assert "Enabled sources: pyth, aster" in captured.out


def test_parser_preserves_shared_config_before_subcommand() -> None:
    args = build_parser().parse_args(["--config", "/tmp/custom-config.yaml", "start"])

    assert args.config == "/tmp/custom-config.yaml"


def test_cli_defaults_to_status_and_shows_start_hint(tmp_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.setattr(
        "market_recorder.cli.read_service_status",
    lambda instance: _service_status(
      instance,
            state="stopped",
            message="Recorder service is not running.",
        ),
    )

    exit_code = main([])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Recorder service status" in captured.out
    assert "Hint: run 'market-recorder start'" in captured.out


def test_cli_rejects_runtime_overrides_for_service_commands(capsys) -> None:
    exit_code = main(["--config", "/tmp/custom-config.yaml", "start"])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "do not accept runtime config overrides" in captured.err


def test_cli_start_does_not_load_config(capsys, monkeypatch) -> None:
  def fail_load_config(*args, **kwargs):
    raise AssertionError("load_config should not run for start")

  monkeypatch.setattr("market_recorder.cli.load_config", fail_load_config)
  monkeypatch.setattr(
    "market_recorder.cli.start_service",
    lambda instance: _service_status(
      instance,
      state="running",
      pid=1234,
      message="Recorder service is running.",
    ),
  )

  exit_code = main(["start"])
  captured = capsys.readouterr()

  assert exit_code == 0
  assert "Recorder service is running." in captured.out


def test_cli_restart_does_not_load_config(capsys, monkeypatch) -> None:
  def fail_load_config(*args, **kwargs):
    raise AssertionError("load_config should not run for restart")

  monkeypatch.setattr("market_recorder.cli.load_config", fail_load_config)
  monkeypatch.setattr(
    "market_recorder.cli.restart_service",
    lambda instance: _service_status(
      instance,
      state="running",
      pid=5678,
      message="Recorder service restarted.",
    ),
  )

  exit_code = main(["restart"])
  captured = capsys.readouterr()

  assert exit_code == 0
  assert "Recorder service restarted." in captured.out


def test_cli_reports_invalid_config_to_stderr(tmp_path: Path, capsys) -> None:
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
    path: webhook/tradingview
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

    exit_code = main(["validate-config", "--config", str(config_path)])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "Configuration error:" in captured.err


def test_cli_write_sample_creates_valid_raw_file(tmp_path: Path, capsys) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        f"""
runtime:
  environment: development
  timezone: UTC
  data_root: {tmp_path / 'data'}
  sources_config: {Path('config/sources.example.yaml').resolve()}
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

    exit_code = main(["write-sample", "--config", str(config_path)])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Sample raw file:" in captured.out

    raw_path = Path(captured.out.splitlines()[0].split(": ", 1)[1])
    summary = validate_raw_file(raw_path)
    assert summary.record_count == 2


def test_cli_validate_raw_rejects_active_segment(tmp_path: Path, capsys) -> None:
    route = RawStreamRoute(source="sample", transport="internal", source_symbol="BTCUSD", stream="price_stream")
    writer = RawJsonlZstWriter(
      data_root=tmp_path,
      route=route,
      run_id="sample-run",
      compression_level=3,
    )
    active_path = writer.write_record(
      build_market_event(
        source=route.source,
        transport=route.transport,
        stream=route.stream,
        stream_name=None,
        canonical_symbol="BTCUSD",
        source_symbol=route.source_symbol,
        conn_id="sample-conn",
        seq=1,
        payload={"price": "1"},
        ts_recv_ns=1,
        ts_recv_utc="2026-04-30T14:00:00Z",
        monotonic_value=1,
      ),
    )
    writer.flush()

    exit_code = main(["validate-raw", str(active_path)])
    captured = capsys.readouterr()

    writer.close()

    assert exit_code == 1
    assert "Validation error:" in captured.err
    assert "Refusing to validate active raw segment" in captured.err


def test_cli_serve_tradingview_passes_unstarted_runtime(tmp_path: Path, capsys, monkeypatch) -> None:
    observed: dict[str, bool] = {}

    async def fake_serve_tradingview_webhook(**kwargs) -> TradingViewWebhookSummary:
        runtime = kwargs["runtime"]
        observed["runner_started"] = runtime._runner is not None
        return TradingViewWebhookSummary(
            request_count=0,
            error_record_count=0,
            bind_host="127.0.0.1",
            bind_port=18080,
            path="/webhook/test",
            output_paths=(),
        )

    monkeypatch.setattr(
        "market_recorder.cli.serve_tradingview_webhook",
        fake_serve_tradingview_webhook,
    )

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

    exit_code = main([
        "serve-tradingview",
        "--config",
        str(config_path),
        "--duration-seconds",
        "0.01",
    ])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert observed["runner_started"] is False
    assert "TradingView webhook server complete" in captured.out


def test_cli_restart_reports_restarted_service(capsys, monkeypatch) -> None:
    restarted_status = _service_status(
        "main",
        state="running",
        pid=9876,
        run_id="recorder-test",
        config_path=Path("/etc/market-recorder/main.env"),
        data_root=Path("/var/lib/market-recorder/main"),
        health_path=Path("/var/lib/market-recorder/main/manifests/runtime/health.json"),
        started_at_utc="2026-04-30T00:00:00Z",
        updated_at_utc="2026-04-30T00:00:10Z",
        message="Recorder service restarted.",
    )

    monkeypatch.setattr("market_recorder.cli.restart_service", lambda instance: restarted_status)

    exit_code = main(["restart"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Recorder service status" in captured.out
    assert "Recorder service restarted." in captured.out