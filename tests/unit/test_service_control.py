from __future__ import annotations

import asyncio
import json
from pathlib import Path

from market_recorder.config import apply_runtime_overrides, load_config
from market_recorder.control_socket import request_control
from market_recorder.service_control import (
    build_service_launch_spec,
    build_service_worker_command,
    build_service_worker_env,
    default_instance,
    default_socket_path,
    read_service_status,
    run_service_worker_foreground,
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


def test_default_socket_path_uses_instance() -> None:
    assert default_instance() == "main"
    assert default_socket_path("copilot") == Path("/run/market-recorder/copilot/control.sock")


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


def test_build_service_worker_env_forces_unbuffered_python() -> None:
    env = build_service_worker_env({"PATH": "/usr/bin"})
    assert env["PYTHONUNBUFFERED"] == "1"
    assert env["PATH"] == "/usr/bin"

    preserved = build_service_worker_env({"PATH": "/usr/bin", "PYTHONUNBUFFERED": "0"})
    assert preserved["PYTHONUNBUFFERED"] == "0"


def test_read_service_status_reports_stopped_without_socket() -> None:
    status = read_service_status("main")

    assert status.state == "stopped"
    assert status.pid is None
    assert status.available_via_socket is False


def test_run_service_worker_foreground_exposes_control_socket(tmp_path: Path, monkeypatch) -> None:
    async def fake_run_recorder_service(**kwargs):
        runtime = kwargs["runtime"]
        health_path = kwargs["health_path"]
        health_path.parent.mkdir(parents=True, exist_ok=True)
        health_path.write_text(
            json.dumps(
                {
                    "run_id": runtime.run_id,
                    "updated_at_utc": "2026-04-30T00:00:05Z",
                    "enabled_components": [],
                    "component_statuses": {},
                    "component_outputs": {},
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        on_ready = kwargs.get("on_ready")
        if on_ready is not None:
            maybe_result = on_ready()
            if maybe_result is not None:
                await maybe_result
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            raise

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
    socket_path = tmp_path / "runtime" / "control.sock"

    async def exercise_worker() -> int:
        worker_task = asyncio.create_task(
            run_service_worker_foreground(
                config,
                health_interval_seconds=1.0,
                health_path=None,
                duration_seconds=None,
            ),
        )

        deadline = asyncio.get_running_loop().time() + 5.0
        while not socket_path.exists():
            if asyncio.get_running_loop().time() >= deadline:
                raise AssertionError("Control socket was not created in time")
            await asyncio.sleep(0.05)

        ping_response = await asyncio.to_thread(request_control, socket_path, "ping")
        status_response = await asyncio.to_thread(request_control, socket_path, "status")
        health_response = await asyncio.to_thread(request_control, socket_path, "health")
        stop_response = await asyncio.to_thread(request_control, socket_path, "stop")
        exit_code = await worker_task

        assert ping_response["ok"] is True
        assert ping_response["message"] == "pong"
        assert status_response["status"]["status"] == "running"
        assert health_response["health"]["run_id"].startswith("recorder-")
        assert stop_response["status"]["status"] == "stopping"
        return exit_code

    monkeypatch.setenv("MARKET_RECORDER_CONTROL_SOCKET", str(socket_path))
    monkeypatch.setenv("MARKET_RECORDER_INSTANCE", "test")
    exit_code = asyncio.run(exercise_worker())

    assert exit_code == 0
    assert not socket_path.exists()