from __future__ import annotations

import asyncio
from pathlib import Path

from market_recorder.config import apply_runtime_overrides, load_config
from market_recorder.service_control import (
    RecorderServiceState,
    build_service_launch_spec,
    build_service_worker_command,
    default_service_paths,
    read_service_state,
    read_service_status,
  run_service_worker_foreground,
    write_service_state,
)


def test_apply_runtime_overrides_updates_data_root_and_log_level(tmp_path: Path) -> None:
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
    overridden = apply_runtime_overrides(
        config,
        data_root="override-data",
        log_level="debug",
    )

    assert overridden.runtime.data_root == (tmp_path / "override-data").resolve()
    assert overridden.logging.level == "DEBUG"
    assert config.runtime.data_root != overridden.runtime.data_root


def test_service_paths_are_repo_scoped(tmp_path: Path) -> None:
    paths = default_service_paths(tmp_path)

    assert paths.state_path == tmp_path / "data" / "service" / "recorder-service.json"
    assert paths.lock_path == tmp_path / "data" / "service" / "recorder-service.lock"
    assert paths.log_path == tmp_path / "data" / "service" / "recorder-service.log"


def test_service_state_round_trip_and_launch_spec(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    state = RecorderServiceState(
        pid=1234,
        status="running",
        run_id="recorder-test",
        config_path=tmp_path / "config.yaml",
        sources_path=tmp_path / "sources.yaml",
        repo_root=tmp_path,
        data_root=tmp_path / "runtime-data",
        log_level="INFO",
        structured_logging=False,
        health_interval_seconds=15.0,
        duration_seconds=60.0,
        health_path_override=None,
        health_path=tmp_path / "runtime-data" / "health.json",
        worker_log_path=tmp_path / "data" / "service" / "recorder-service.log",
        started_at_utc="2026-04-30T00:00:00Z",
        updated_at_utc="2026-04-30T00:00:10Z",
        finished_at_utc=None,
        message="Recorder service is running.",
    )

    write_service_state(state_path, state)
    loaded = read_service_state(state_path)
    assert loaded == state

    launch_spec = loaded.to_launch_spec()
    assert launch_spec.repo_root == tmp_path
    assert launch_spec.data_root == tmp_path / "runtime-data"
    assert launch_spec.health_interval_seconds == 15.0
    assert launch_spec.duration_seconds == 60.0


def test_build_service_worker_command_uses_module_invocation(tmp_path: Path) -> None:
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
    launch_spec = build_service_launch_spec(config, health_interval_seconds=5.0, duration_seconds=30.0)
    command = build_service_worker_command(launch_spec, python_executable="/usr/bin/python3")

    assert command[:3] == ["/usr/bin/python3", "-m", "market_recorder.cli"]
    assert "service-worker" in command
    assert "--duration-seconds" in command
    assert "--data-root" in command


def test_read_service_status_reports_stopped_without_state(tmp_path: Path) -> None:
    status = read_service_status(tmp_path)

    assert status.state == "stopped"
    assert status.pid is None
    assert status.service_state is None


def test_run_service_worker_foreground_writes_terminal_state(tmp_path: Path, monkeypatch) -> None:
    async def fake_run_recorder_service(**kwargs):
        runtime = kwargs["runtime"]
        assert runtime.run_id.startswith("recorder-")
        return {"kind": "service"}

    monkeypatch.setattr("market_recorder.service_control.run_recorder_service", fake_run_recorder_service)

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
    exit_code = asyncio.run(
        run_service_worker_foreground(
            config,
            health_interval_seconds=1.0,
            health_path=None,
            duration_seconds=0.01,
        ),
    )
    paths = default_service_paths(tmp_path)
    state = read_service_state(paths.state_path)

    assert exit_code == 0
    assert state is not None
    assert state.status == "stopped"
    assert state.run_id is not None