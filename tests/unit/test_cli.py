from __future__ import annotations

from pathlib import Path

from market_recorder.alerts import TradingViewWebhookSummary
from market_recorder.cli import build_parser, main
from market_recorder.service_control import (
  RecorderServiceState,
  RecorderServiceStatus,
  default_service_paths,
)
from market_recorder.storage import validate_raw_file


def _service_status(
  tmp_path: Path,
  *,
  state: str,
  pid: int | None = None,
  service_state: RecorderServiceState | None = None,
  message: str | None = None,
) -> RecorderServiceStatus:
  paths = default_service_paths(tmp_path)
  return RecorderServiceStatus(
    state=state,
    state_path=paths.state_path,
    lock_path=paths.lock_path,
    log_path=paths.log_path,
    pid=pid,
    run_id=None if service_state is None else service_state.run_id,
    message=message,
    service_state=service_state,
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
        lambda repo_root: _service_status(
            tmp_path,
            state="stopped",
            message="Recorder service is not running.",
        ),
    )

    exit_code = main([])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Recorder service status" in captured.out
    assert "Hint: run 'market-recorder start'" in captured.out


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


def test_cli_restart_reuses_saved_launch_spec_without_new_overrides(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    service_state = RecorderServiceState(
        pid=4321,
        status="running",
        run_id="recorder-test",
        config_path=tmp_path / "saved-config.yaml",
        sources_path=tmp_path / "saved-sources.yaml",
        repo_root=tmp_path,
        data_root=tmp_path / "saved-data",
        log_level="WARNING",
        structured_logging=False,
        health_interval_seconds=30.0,
        duration_seconds=120.0,
        health_path_override=None,
        health_path=tmp_path / "saved-data" / "health.json",
        worker_log_path=tmp_path / "data" / "service" / "recorder-service.log",
        started_at_utc="2026-04-30T00:00:00Z",
        updated_at_utc="2026-04-30T00:00:10Z",
        finished_at_utc=None,
        message="Recorder service is running.",
    )
    running_status = _service_status(
        tmp_path,
        state="running",
        pid=service_state.pid,
        service_state=service_state,
        message=service_state.message,
    )
    started_status = _service_status(
        tmp_path,
        state="running",
        pid=9876,
        service_state=service_state,
        message="Recorder service restarted.",
    )
    observed: dict[str, object] = {}

    monkeypatch.setattr(
        "market_recorder.cli.read_service_status",
        lambda repo_root: running_status,
    )
    monkeypatch.setattr(
        "market_recorder.cli.stop_background_service",
        lambda repo_root: _service_status(tmp_path, state="stopped", message="Recorder service stopped."),
    )

    def fake_start_background_service(launch_spec):
        observed["launch_spec"] = launch_spec
        return started_status

    monkeypatch.setattr(
        "market_recorder.cli.start_background_service",
        fake_start_background_service,
    )

    exit_code = main(["restart"])
    captured = capsys.readouterr()

    launch_spec = observed["launch_spec"]
    assert exit_code == 0
    assert launch_spec.config_path == service_state.config_path
    assert launch_spec.sources_path == service_state.sources_path
    assert launch_spec.data_root == service_state.data_root
    assert launch_spec.log_level == service_state.log_level
    assert "Recorder service status" in captured.out