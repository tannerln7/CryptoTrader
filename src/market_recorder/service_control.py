"""Background service control helpers for the recorder worker."""

from __future__ import annotations

import asyncio
import errno
import json
import os
import signal
import subprocess
import sys
from contextlib import suppress
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from time import monotonic, sleep
from typing import Any, TextIO

try:
    import fcntl
except ImportError:  # pragma: no cover - non-Unix platforms
    fcntl = None

from .config import RecorderConfig
from .logging import configure_logging
from .runtime import RecorderRuntime
from .service import default_health_manifest_path, run_recorder_service
from .timeutil import utc_now_iso

_RUNNING_STATES = frozenset({"starting", "running", "stopping"})
_TERMINAL_STATES = frozenset({"stopped", "failed"})


class ServiceControlError(RuntimeError):
    """Raised when service control operations fail."""


@dataclass(frozen=True, slots=True)
class RecorderServicePaths:
    state_path: Path
    lock_path: Path
    log_path: Path


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
class RecorderServiceState:
    pid: int | None
    status: str
    run_id: str | None
    config_path: Path
    sources_path: Path
    repo_root: Path
    data_root: Path
    log_level: str
    structured_logging: bool
    health_interval_seconds: float
    duration_seconds: float | None
    health_path_override: Path | None
    health_path: Path | None
    worker_log_path: Path
    started_at_utc: str | None
    updated_at_utc: str
    finished_at_utc: str | None
    message: str | None

    def to_json_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key, value in list(payload.items()):
            if isinstance(value, Path):
                payload[key] = str(value)
        return payload

    @classmethod
    def from_json_dict(cls, payload: dict[str, Any]) -> "RecorderServiceState":
        try:
            return cls(
                pid=payload.get("pid"),
                status=str(payload["status"]),
                run_id=payload.get("run_id"),
                config_path=Path(payload["config_path"]),
                sources_path=Path(payload["sources_path"]),
                repo_root=Path(payload["repo_root"]),
                data_root=Path(payload["data_root"]),
                log_level=str(payload["log_level"]),
                structured_logging=bool(payload["structured_logging"]),
                health_interval_seconds=float(payload["health_interval_seconds"]),
                duration_seconds=(
                    None
                    if payload.get("duration_seconds") is None
                    else float(payload["duration_seconds"])
                ),
                health_path_override=(
                    None
                    if payload.get("health_path_override") is None
                    else Path(payload["health_path_override"])
                ),
                health_path=(
                    None
                    if payload.get("health_path") is None
                    else Path(payload["health_path"])
                ),
                worker_log_path=Path(payload["worker_log_path"]),
                started_at_utc=payload.get("started_at_utc"),
                updated_at_utc=str(payload["updated_at_utc"]),
                finished_at_utc=payload.get("finished_at_utc"),
                message=payload.get("message"),
            )
        except KeyError as exc:
            raise ServiceControlError(f"Service state file is missing required field {exc.args[0]!r}") from exc
        except (TypeError, ValueError) as exc:
            raise ServiceControlError(f"Service state file is invalid: {exc}") from exc

    def to_launch_spec(self) -> RecorderServiceLaunchSpec:
        return RecorderServiceLaunchSpec(
            config_path=self.config_path,
            sources_path=self.sources_path,
            repo_root=self.repo_root,
            data_root=self.data_root,
            log_level=self.log_level,
            structured_logging=self.structured_logging,
            health_interval_seconds=self.health_interval_seconds,
            duration_seconds=self.duration_seconds,
            health_path_override=self.health_path_override,
        )


@dataclass(frozen=True, slots=True)
class RecorderServiceStatus:
    state: str
    state_path: Path
    lock_path: Path
    log_path: Path
    pid: int | None
    run_id: str | None
    message: str | None
    service_state: RecorderServiceState | None

    @property
    def is_running(self) -> bool:
        return self.state in _RUNNING_STATES


def default_service_paths(repo_root: Path) -> RecorderServicePaths:
    control_root = repo_root / "data" / "service"
    return RecorderServicePaths(
        state_path=control_root / "recorder-service.json",
        lock_path=control_root / "recorder-service.lock",
        log_path=control_root / "recorder-service.log",
    )


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


def read_service_state(state_path: Path) -> RecorderServiceState | None:
    if not state_path.exists():
        return None

    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ServiceControlError(f"Failed to parse service state file {state_path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise ServiceControlError(f"Service state file must contain a JSON object: {state_path}")
    return RecorderServiceState.from_json_dict(payload)


def write_service_state(state_path: Path, state: RecorderServiceState) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state.to_json_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_service_status(repo_root: Path) -> RecorderServiceStatus:
    paths = default_service_paths(repo_root)
    state = read_service_state(paths.state_path)
    lock_held = _is_lock_held(paths.lock_path)

    if state is None:
        if lock_held:
            return RecorderServiceStatus(
                state="starting",
                state_path=paths.state_path,
                lock_path=paths.lock_path,
                log_path=paths.log_path,
                pid=None,
                run_id=None,
                message="Recorder service lock is held but state has not been written yet.",
                service_state=None,
            )
        return RecorderServiceStatus(
            state="stopped",
            state_path=paths.state_path,
            lock_path=paths.lock_path,
            log_path=paths.log_path,
            pid=None,
            run_id=None,
            message="Recorder service is not running.",
            service_state=None,
        )

    pid_running = state.pid is not None and _is_process_running(state.pid)
    if pid_running:
        resolved_state = state.status if state.status in _RUNNING_STATES else "running"
        message = state.message
    elif state.status in _TERMINAL_STATES:
        resolved_state = state.status
        message = state.message
    elif lock_held:
        resolved_state = "starting"
        message = state.message or "Recorder service is starting."
    else:
        resolved_state = "stale"
        message = state.message or "Recorder service state is stale; the recorded PID is not running."

    return RecorderServiceStatus(
        state=resolved_state,
        state_path=paths.state_path,
        lock_path=paths.lock_path,
        log_path=paths.log_path,
        pid=state.pid,
        run_id=state.run_id,
        message=message,
        service_state=state,
    )


def load_service_health(repo_root: Path) -> tuple[RecorderServiceStatus, dict[str, Any] | None]:
    status = read_service_status(repo_root)
    state = status.service_state
    if state is None or state.health_path is None or not state.health_path.exists():
        return status, None

    try:
        payload = json.loads(state.health_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ServiceControlError(f"Failed to parse health manifest {state.health_path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise ServiceControlError(f"Health manifest must contain a JSON object: {state.health_path}")
    return status, payload


def start_background_service(
    launch_spec: RecorderServiceLaunchSpec,
    *,
    python_executable: str | Path | None = None,
    startup_timeout_seconds: float = 5.0,
) -> RecorderServiceStatus:
    status = read_service_status(launch_spec.repo_root)
    if status.is_running:
        raise ServiceControlError(f"Recorder service is already running with PID {status.pid}.")

    paths = default_service_paths(launch_spec.repo_root)
    paths.log_path.parent.mkdir(parents=True, exist_ok=True)
    log_handle = paths.log_path.open("a", encoding="utf-8")
    try:
        process = subprocess.Popen(
            build_service_worker_command(launch_spec, python_executable=python_executable),
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            cwd=str(launch_spec.repo_root),
            close_fds=True,
            start_new_session=True,
            text=True,
        )
    finally:
        log_handle.close()

    deadline = monotonic() + startup_timeout_seconds
    while monotonic() < deadline:
        current = read_service_status(launch_spec.repo_root)
        if current.service_state is not None and current.service_state.pid == process.pid:
            if current.state in {"starting", "running"}:
                return current
            if current.state == "failed":
                raise ServiceControlError(current.message or "Recorder service failed to start.")
        if process.poll() is not None:
            current = read_service_status(launch_spec.repo_root)
            if current.is_running:
                return current
            raise ServiceControlError(
                current.message
                or f"Recorder service exited during startup with code {process.returncode}. See {paths.log_path}.",
            )
        sleep(0.1)

    current = read_service_status(launch_spec.repo_root)
    if current.service_state is not None and current.service_state.pid == process.pid:
        return current
    raise ServiceControlError(f"Recorder service did not report startup state within {startup_timeout_seconds} seconds.")


def stop_background_service(repo_root: Path, *, timeout_seconds: float = 15.0) -> RecorderServiceStatus:
    status = read_service_status(repo_root)
    if not status.is_running or status.pid is None:
        return status

    try:
        os.kill(status.pid, signal.SIGTERM)
    except ProcessLookupError:
        return read_service_status(repo_root)

    deadline = monotonic() + timeout_seconds
    while monotonic() < deadline:
        if not _is_process_running(status.pid):
            return read_service_status(repo_root)
        sleep(0.1)
    raise ServiceControlError(f"Recorder service PID {status.pid} did not stop within {timeout_seconds} seconds.")


async def run_service_worker_foreground(
    config: RecorderConfig,
    *,
    health_interval_seconds: float,
    health_path: Path | None,
    duration_seconds: float | None,
) -> int:
    if fcntl is None:  # pragma: no cover - non-Unix platforms
        raise ServiceControlError("Background service control requires Unix fcntl support.")

    launch_spec = build_service_launch_spec(
        config,
        health_interval_seconds=health_interval_seconds,
        health_path=health_path,
        duration_seconds=duration_seconds,
    )
    paths = default_service_paths(config.repo_root)
    lock_handle = _try_acquire_lock(paths.lock_path)
    if lock_handle is None:
        raise ServiceControlError("Recorder service is already running.")

    runtime = RecorderRuntime.from_config(config)
    actual_health_path = launch_spec.health_path_override or default_health_manifest_path(
        config.runtime.data_root,
        runtime.run_id,
    )
    pid = os.getpid()
    started_at_utc = utc_now_iso()
    state = RecorderServiceState(
        pid=pid,
        status="starting",
        run_id=runtime.run_id,
        config_path=launch_spec.config_path,
        sources_path=launch_spec.sources_path,
        repo_root=launch_spec.repo_root,
        data_root=launch_spec.data_root,
        log_level=launch_spec.log_level,
        structured_logging=launch_spec.structured_logging,
        health_interval_seconds=launch_spec.health_interval_seconds,
        duration_seconds=launch_spec.duration_seconds,
        health_path_override=launch_spec.health_path_override,
        health_path=actual_health_path,
        worker_log_path=paths.log_path,
        started_at_utc=started_at_utc,
        updated_at_utc=utc_now_iso(),
        finished_at_utc=None,
        message="Recorder service is starting.",
    )
    write_service_state(paths.state_path, state)

    configure_logging(config.logging.level, structured=config.logging.structured)
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()
    _install_signal_handlers(loop, stop_event)

    service_task = asyncio.create_task(
        run_recorder_service(
            runtime=runtime,
            duration_seconds=duration_seconds,
            health_interval_seconds=health_interval_seconds,
            health_path=actual_health_path,
        ),
        name="recorder-service",
    )
    stop_task = asyncio.create_task(stop_event.wait(), name="recorder-service-stop")

    exit_code = 0
    final_status = "stopped"
    final_message = "Recorder service exited cleanly."
    try:
        await asyncio.sleep(0)
        if service_task.done():
            await service_task

        state = replace(
            state,
            status="running",
            updated_at_utc=utc_now_iso(),
            message="Recorder service is running.",
        )
        write_service_state(paths.state_path, state)

        done, _ = await asyncio.wait({service_task, stop_task}, return_when=asyncio.FIRST_COMPLETED)
        if stop_task in done and not service_task.done():
            state = replace(
                state,
                status="stopping",
                updated_at_utc=utc_now_iso(),
                message="Recorder service is stopping.",
            )
            write_service_state(paths.state_path, state)
            service_task.cancel()

        try:
            await service_task
            if stop_task in done:
                final_message = "Recorder service stopped by signal."
        except asyncio.CancelledError:
            final_message = "Recorder service stopped by signal."
        except Exception as exc:
            exit_code = 1
            final_status = "failed"
            final_message = f"{exc.__class__.__name__}: {exc}"
    finally:
        stop_task.cancel()
        with suppress(asyncio.CancelledError):
            await stop_task
        await runtime.close()
        final_state = replace(
            state,
            status=final_status,
            updated_at_utc=utc_now_iso(),
            finished_at_utc=utc_now_iso(),
            message=final_message,
        )
        write_service_state(paths.state_path, final_state)
        _release_lock(lock_handle)

    return exit_code


def _try_acquire_lock(lock_path: Path) -> TextIO | None:
    if fcntl is None:  # pragma: no cover - non-Unix platforms
        raise ServiceControlError("Background service control requires Unix fcntl support.")

    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        handle.close()
        if exc.errno in (errno.EACCES, errno.EAGAIN):
            return None
        raise
    return handle


def _release_lock(handle: TextIO) -> None:
    if fcntl is None:  # pragma: no cover - non-Unix platforms
        handle.close()
        return
    with suppress(OSError):
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    handle.close()


def _is_lock_held(lock_path: Path) -> bool:
    if fcntl is None:  # pragma: no cover - non-Unix platforms
        return False

    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+", encoding="utf-8")
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if exc.errno in (errno.EACCES, errno.EAGAIN):
                return True
            raise
        return False
    finally:
        with suppress(OSError):
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def _is_process_running(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _install_signal_handlers(loop: asyncio.AbstractEventLoop, stop_event: asyncio.Event) -> None:
    def request_stop() -> None:
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        with suppress(NotImplementedError, RuntimeError, ValueError):
            loop.add_signal_handler(sig, request_stop)