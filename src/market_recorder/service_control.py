"""Systemd and control-socket helpers for the recorder worker."""

from __future__ import annotations

import asyncio
import json
import os
import signal
import subprocess
import sys
from contextlib import suppress
from dataclasses import asdict, dataclass
from grp import getgrnam
from pathlib import Path
from time import monotonic, sleep
from typing import Any

from .config import RecorderConfig
from .control_socket import ControlSocketServer, SocketUnavailableError, request_control
from .logging import configure_logging
from .runtime import RecorderRuntime
from .service import default_health_manifest_path, run_recorder_service
from .systemd_notify import notify_ready, notify_status, notify_stopping
from .timeutil import utc_now_iso

_RUNNING_STATES = frozenset({"starting", "running", "stopping"})
_ACTIVE_SYSTEMD_STATES = frozenset({"active", "activating", "deactivating"})
_DEFAULT_INSTANCE = "main"
_DEFAULT_OPERATOR_GROUP = "market-recorder"


class ServiceControlError(RuntimeError):
    """Raised when service control operations fail."""


@dataclass(frozen=True, slots=True)
class RecorderServiceLaunchSpec:
    config_path: Path
    sources_path: Path
    repo_root: Path
    data_root: Path
    log_level: str
    structured_logging: bool
    health_interval_seconds: float
    duration_seconds: float | None
    health_path_override: Path | None = None

    def to_display_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key, value in list(payload.items()):
            if isinstance(value, Path):
                payload[key] = str(value)
        return payload


@dataclass(frozen=True, slots=True)
class RecorderServiceStatus:
    status: str
    instance: str
    unit_name: str
    socket_path: Path
    pid: int | None
    run_id: str | None
    config_path: Path | None
    sources_path: Path | None
    data_root: Path | None
    health_path: Path | None
    started_at_utc: str | None
    updated_at_utc: str | None
    finished_at_utc: str | None
    message: str | None
    available_via_socket: bool

    @property
    def state(self) -> str:
        return self.status

    @property
    def is_running(self) -> bool:
        return self.status in _RUNNING_STATES


@dataclass(slots=True)
class _WorkerControlState:
    instance: str
    unit_name: str
    socket_path: Path
    pid: int
    run_id: str
    config_path: Path
    sources_path: Path
    data_root: Path
    health_path: Path
    started_at_utc: str
    status: str
    message: str
    updated_at_utc: str
    finished_at_utc: str | None = None

    def to_status_payload(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "instance": self.instance,
            "unit_name": self.unit_name,
            "socket_path": str(self.socket_path),
            "pid": self.pid,
            "run_id": self.run_id,
            "config_path": str(self.config_path),
            "sources_path": str(self.sources_path),
            "data_root": str(self.data_root),
            "health_path": str(self.health_path),
            "started_at_utc": self.started_at_utc,
            "updated_at_utc": self.updated_at_utc,
            "finished_at_utc": self.finished_at_utc,
            "message": self.message,
        }


def default_instance() -> str:
    return os.environ.get("MARKET_RECORDER_INSTANCE", _DEFAULT_INSTANCE)


def default_socket_path(instance: str) -> Path:
    return Path("/run/market-recorder") / instance / "control.sock"


def systemd_unit_name(instance: str) -> str:
    return f"market-recorder@{instance}.service"


def build_service_launch_spec(
    config: RecorderConfig,
    *,
    health_interval_seconds: float | None = None,
    health_path: str | Path | None = None,
    duration_seconds: float | None = None,
) -> RecorderServiceLaunchSpec:
    return RecorderServiceLaunchSpec(
        config_path=config.config_path,
        sources_path=config.sources_path,
        repo_root=config.repo_root,
        data_root=config.runtime.data_root,
        log_level=config.logging.level,
        structured_logging=config.logging.structured,
        health_interval_seconds=10.0 if health_interval_seconds is None else health_interval_seconds,
        duration_seconds=duration_seconds,
        health_path_override=None if health_path is None else Path(health_path),
    )


def build_service_worker_command(
    launch_spec: RecorderServiceLaunchSpec,
    *,
    python_executable: str | Path | None = None,
) -> list[str]:
    command = [
        str(python_executable or sys.executable),
        "-m",
        "market_recorder.cli",
        "--config",
        str(launch_spec.config_path),
        "--sources",
        str(launch_spec.sources_path),
        "--data-root",
        str(launch_spec.data_root),
        "--log-level",
        launch_spec.log_level,
        "service-worker",
        "--health-interval-seconds",
        str(launch_spec.health_interval_seconds),
    ]
    if launch_spec.duration_seconds is not None:
        command.extend(["--duration-seconds", str(launch_spec.duration_seconds)])
    if launch_spec.health_path_override is not None:
        command.extend(["--health-path", str(launch_spec.health_path_override)])
    return command


def build_service_worker_env(base_env: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ if base_env is None else base_env)
    env.setdefault("PYTHONUNBUFFERED", "1")
    return env


def read_service_status(instance: str) -> RecorderServiceStatus:
    socket_path = default_socket_path(instance)
    try:
        response = _checked_control_request(socket_path, "status")
    except SocketUnavailableError:
        systemd_state = systemctl_is_active(instance)
        return RecorderServiceStatus(
            status=_normalize_systemd_state(systemd_state),
            instance=instance,
            unit_name=systemd_unit_name(instance),
            socket_path=socket_path,
            pid=systemctl_main_pid(instance),
            run_id=None,
            config_path=None,
            sources_path=None,
            data_root=None,
            health_path=None,
            started_at_utc=None,
            updated_at_utc=None,
            finished_at_utc=None,
            message=_socket_unavailable_message(systemd_state, socket_path),
            available_via_socket=False,
        )

    payload = response.get("status")
    if not isinstance(payload, dict):
        raise ServiceControlError("Control socket status response did not include a status object.")
    return _status_from_payload(payload)


def load_service_health(instance: str) -> tuple[RecorderServiceStatus, dict[str, Any] | None]:
    try:
        response = _checked_control_request(default_socket_path(instance), "health")
    except SocketUnavailableError:
        return read_service_status(instance), None

    payload = response.get("status")
    if not isinstance(payload, dict):
        raise ServiceControlError("Control socket health response did not include a status object.")
    health = response.get("health")
    if health is not None and not isinstance(health, dict):
        raise ServiceControlError("Control socket health response returned invalid health data.")
    return _status_from_payload(payload), health


def start_service(instance: str) -> RecorderServiceStatus:
    systemctl_start(instance)
    socket_path = default_socket_path(instance)
    try:
        _checked_control_request(socket_path, "ping")
    except SocketUnavailableError as exc:
        raise ServiceControlError(
            f"Recorder service started but the control socket at {socket_path} is unavailable: {exc}",
        ) from exc
    return read_service_status(instance)


def stop_service(instance: str, *, timeout_seconds: float = 30.0) -> RecorderServiceStatus:
    status = read_service_status(instance)
    if not status.is_running and status.status != "failed":
        return status

    socket_path = default_socket_path(instance)
    try:
        _checked_control_request(socket_path, "stop")
    except SocketUnavailableError:
        systemctl_stop(instance)

    _wait_for_stop(instance, timeout_seconds=timeout_seconds)
    return read_service_status(instance)


def restart_service(instance: str) -> RecorderServiceStatus:
    status = read_service_status(instance)
    if status.is_running or status.status == "failed":
        stop_service(instance)
    return start_service(instance)


async def run_service_worker_foreground(
    config: RecorderConfig,
    *,
    health_interval_seconds: float,
    health_path: Path | None,
    duration_seconds: float | None,
) -> int:
    launch_spec = build_service_launch_spec(
        config,
        health_interval_seconds=health_interval_seconds,
        health_path=health_path,
        duration_seconds=duration_seconds,
    )
    instance = default_instance()
    socket_path = Path(os.environ.get("MARKET_RECORDER_CONTROL_SOCKET", default_socket_path(instance)))
    operator_group = os.environ.get("MARKET_RECORDER_OPERATOR_GROUP", _DEFAULT_OPERATOR_GROUP)

    runtime = RecorderRuntime.from_config(config)
    actual_health_path = launch_spec.health_path_override or default_health_manifest_path(
        config.runtime.data_root,
        runtime.run_id,
    )
    state = _WorkerControlState(
        instance=instance,
        unit_name=systemd_unit_name(instance),
        socket_path=socket_path,
        pid=os.getpid(),
        run_id=runtime.run_id,
        config_path=launch_spec.config_path,
        sources_path=launch_spec.sources_path,
        data_root=launch_spec.data_root,
        health_path=actual_health_path,
        started_at_utc=utc_now_iso(),
        status="starting",
        message="Recorder service is starting.",
        updated_at_utc=utc_now_iso(),
    )

    configure_logging(config.logging.level, structured=config.logging.structured)
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()
    startup_event = asyncio.Event()
    _install_signal_handlers(loop, stop_event)

    control_server = ControlSocketServer(
        socket_path=socket_path,
        request_handler=lambda request: _handle_control_request(
            request,
            state=state,
            stop_event=stop_event,
        ),
        operator_gid=_lookup_group_id(operator_group),
    )
    await control_server.start()

    service_task = asyncio.create_task(
        run_recorder_service(
            runtime=runtime,
            duration_seconds=duration_seconds,
            health_interval_seconds=health_interval_seconds,
            health_path=actual_health_path,
            on_ready=startup_event.set,
        ),
        name="recorder-service",
    )
    stop_task = asyncio.create_task(stop_event.wait(), name="recorder-service-stop")
    startup_task = asyncio.create_task(startup_event.wait(), name="recorder-service-startup")

    exit_code = 0
    final_status = "stopped"
    final_message = "Recorder service exited cleanly."
    try:
        done, _ = await asyncio.wait(
            {service_task, startup_task, stop_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        if startup_task in done:
            state.status = "running"
            state.updated_at_utc = utc_now_iso()
            state.message = "Recorder service is running."
            notify_ready(status=state.message)
        elif stop_task in done and not service_task.done():
            state.status = "stopping"
            state.updated_at_utc = utc_now_iso()
            state.message = "Recorder service is stopping."
            with suppress(OSError):
                notify_stopping(status=state.message)
            service_task.cancel()

        if not service_task.done() and startup_task.done():
            done, _ = await asyncio.wait(
                {service_task, stop_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if stop_task in done and not service_task.done():
                state.status = "stopping"
                state.updated_at_utc = utc_now_iso()
                state.message = "Recorder service is stopping."
                with suppress(OSError):
                    notify_stopping(status=state.message)
                service_task.cancel()

        try:
            await service_task
            if stop_task.done():
                final_message = "Recorder service stopped by signal."
        except asyncio.CancelledError:
            final_message = "Recorder service stopped by signal."
        except Exception as exc:
            exit_code = 1
            final_status = "failed"
            final_message = f"{exc.__class__.__name__}: {exc}"
    except Exception as exc:
        exit_code = 1
        final_status = "failed"
        final_message = f"{exc.__class__.__name__}: {exc}"
        if not service_task.done():
            service_task.cancel()
            with suppress(asyncio.CancelledError):
                await service_task
    finally:
        stop_task.cancel()
        startup_task.cancel()
        with suppress(asyncio.CancelledError):
            await stop_task
        with suppress(asyncio.CancelledError):
            await startup_task
        with suppress(OSError):
            notify_stopping(status=final_message)
        await control_server.close()
        await runtime.close()
        state.status = final_status
        state.updated_at_utc = utc_now_iso()
        state.finished_at_utc = utc_now_iso()
        state.message = final_message

    return exit_code


def systemctl_start(instance: str) -> None:
    _run_systemctl(["start", systemd_unit_name(instance)], check=True)


def systemctl_stop(instance: str) -> None:
    _run_systemctl(["stop", systemd_unit_name(instance)], check=True)


def systemctl_is_active(instance: str) -> str:
    result = _run_systemctl(["is-active", systemd_unit_name(instance)], check=False)
    state = (result.stdout or result.stderr).strip()
    return state or "unknown"


def systemctl_main_pid(instance: str) -> int | None:
    result = _run_systemctl(["show", "--property=MainPID", "--value", systemd_unit_name(instance)], check=False)
    value = (result.stdout or "").strip()
    if not value:
        return None
    try:
        pid = int(value)
    except ValueError:
        return None
    return pid if pid > 0 else None


def _run_systemctl(args: list[str], *, check: bool) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["systemctl", *args],
        capture_output=True,
        check=False,
        text=True,
    )
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise ServiceControlError(detail or f"systemctl {' '.join(args)} failed with exit code {result.returncode}.")
    return result


def _normalize_systemd_state(systemd_state: str) -> str:
    mapping = {
        "active": "running",
        "activating": "starting",
        "deactivating": "stopping",
        "inactive": "stopped",
        "failed": "failed",
    }
    return mapping.get(systemd_state, systemd_state or "unknown")


def _socket_unavailable_message(systemd_state: str, socket_path: Path) -> str:
    normalized_state = _normalize_systemd_state(systemd_state)
    if systemd_state in _ACTIVE_SYSTEMD_STATES:
        return f"Recorder service is {normalized_state}, but the control socket at {socket_path} is unavailable."
    if normalized_state == "failed":
        return "Recorder service failed. Inspect systemctl status or journalctl for details."
    return "Recorder service is not running."


def _status_from_payload(payload: dict[str, Any]) -> RecorderServiceStatus:
    return RecorderServiceStatus(
        status=str(payload.get("status", "unknown")),
        instance=str(payload.get("instance", default_instance())),
        unit_name=str(payload.get("unit_name", systemd_unit_name(default_instance()))),
        socket_path=Path(str(payload.get("socket_path", default_socket_path(default_instance())))),
        pid=payload.get("pid"),
        run_id=payload.get("run_id"),
        config_path=_optional_path(payload.get("config_path")),
        sources_path=_optional_path(payload.get("sources_path")),
        data_root=_optional_path(payload.get("data_root")),
        health_path=_optional_path(payload.get("health_path")),
        started_at_utc=payload.get("started_at_utc"),
        updated_at_utc=payload.get("updated_at_utc"),
        finished_at_utc=payload.get("finished_at_utc"),
        message=payload.get("message"),
        available_via_socket=True,
    )


def _optional_path(value: Any) -> Path | None:
    if value in {None, ""}:
        return None
    return Path(str(value))


def _lookup_group_id(group_name: str) -> int | None:
    try:
        return getgrnam(group_name).gr_gid
    except KeyError:
        return None


async def _handle_control_request(
    request: dict[str, Any],
    *,
    state: _WorkerControlState,
    stop_event: asyncio.Event,
) -> dict[str, Any]:
    command = request.get("command")
    if command == "ping":
        return {"message": "pong"}
    if command == "status":
        state.updated_at_utc = utc_now_iso()
        return {"status": state.to_status_payload()}
    if command == "health":
        state.updated_at_utc = utc_now_iso()
        return {
            "status": state.to_status_payload(),
            "health": _read_health_payload(state.health_path),
        }
    if command == "stop":
        state.status = "stopping"
        state.updated_at_utc = utc_now_iso()
        state.message = "Recorder service is stopping."
        with suppress(OSError):
            notify_status(state.message)
        stop_event.set()
        return {
            "message": "Recorder service stop requested.",
            "status": state.to_status_payload(),
        }
    raise ServiceControlError(f"Unsupported control command {command!r}.")


def _checked_control_request(socket_path: Path, command: str) -> dict[str, Any]:
    response = request_control(socket_path, command)
    if response.get("ok") is False:
        raise ServiceControlError(response.get("error") or f"Control command {command!r} failed.")
    return response


def _read_health_payload(health_path: Path) -> dict[str, Any] | None:
    if not health_path.exists():
        return None
    try:
        payload = json.loads(health_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ServiceControlError(f"Failed to parse health manifest {health_path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ServiceControlError(f"Health manifest must contain a JSON object: {health_path}")
    return payload


def _wait_for_stop(instance: str, *, timeout_seconds: float) -> None:
    deadline = monotonic() + timeout_seconds
    while monotonic() < deadline:
        if systemctl_is_active(instance) not in _ACTIVE_SYSTEMD_STATES:
            return
        sleep(0.1)
    raise ServiceControlError(
        f"Recorder service {systemd_unit_name(instance)} did not stop within {timeout_seconds} seconds.",
    )


def _install_signal_handlers(loop: asyncio.AbstractEventLoop, stop_event: asyncio.Event) -> None:
    def _request_stop() -> None:
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        with suppress(NotImplementedError):
            loop.add_signal_handler(sig, _request_stop)