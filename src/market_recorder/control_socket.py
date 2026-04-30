"""Unix domain control socket helpers for the recorder service."""

from __future__ import annotations

import asyncio
import json
import os
import socket
import stat
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

MAX_CONTROL_MESSAGE_BYTES = 8192
DEFAULT_CONTROL_TIMEOUT_SECONDS = 5.0


class ControlSocketError(RuntimeError):
    """Raised when control socket communication fails."""


class SocketUnavailableError(ControlSocketError):
    """Raised when the control socket is unavailable."""


ControlRequestHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


class ControlSocketServer:
    """Serve newline-delimited JSON control requests over a Unix socket."""

    def __init__(
        self,
        *,
        socket_path: Path,
        request_handler: ControlRequestHandler,
        operator_gid: int | None = None,
        socket_mode: int = 0o660,
        timeout_seconds: float = DEFAULT_CONTROL_TIMEOUT_SECONDS,
    ) -> None:
        self.socket_path = socket_path
        self.request_handler = request_handler
        self.operator_gid = operator_gid
        self.socket_mode = socket_mode
        self.timeout_seconds = timeout_seconds
        self._server: asyncio.AbstractServer | None = None

    async def start(self) -> None:
        self.socket_path.parent.mkdir(parents=True, exist_ok=True)
        self._unlink_existing_socket()
        self._server = await asyncio.start_unix_server(
            self._handle_connection,
            path=str(self.socket_path),
        )
        os.chmod(self.socket_path, self.socket_mode)
        if self.operator_gid is not None:
            os.chown(self.socket_path, -1, self.operator_gid)

    async def close(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        self._unlink_socket_path()

    async def _handle_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        try:
            data = await asyncio.wait_for(reader.readline(), timeout=self.timeout_seconds)
            if not data:
                response = {"ok": False, "error": "No control request received."}
            elif len(data) > MAX_CONTROL_MESSAGE_BYTES:
                response = {"ok": False, "error": "Control request exceeded maximum size."}
            else:
                response = await self._dispatch_request(data)
        except asyncio.TimeoutError:
            response = {"ok": False, "error": "Timed out waiting for control request."}
        except Exception as exc:  # pragma: no cover - defensive guardrail
            response = {"ok": False, "error": f"{exc.__class__.__name__}: {exc}"}

        writer.write(json.dumps(response, sort_keys=True).encode("utf-8") + b"\n")
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    async def _dispatch_request(self, data: bytes) -> dict[str, Any]:
        try:
            request = json.loads(data.decode("utf-8"))
        except json.JSONDecodeError as exc:
            return {"ok": False, "error": f"Invalid JSON control request: {exc}"}

        if not isinstance(request, dict):
            return {"ok": False, "error": "Control request must be a JSON object."}

        try:
            response = await self.request_handler(request)
        except Exception as exc:
            return {"ok": False, "error": f"{exc.__class__.__name__}: {exc}"}

        if not isinstance(response, dict):
            return {"ok": False, "error": "Control handler returned a non-object response."}
        if "ok" not in response:
            response = {"ok": True, **response}
        return response

    def _unlink_existing_socket(self) -> None:
        if not self.socket_path.exists():
            return
        if stat.S_ISSOCK(self.socket_path.stat().st_mode):
            self.socket_path.unlink()
            return
        raise ControlSocketError(
            f"Refusing to replace non-socket path at {self.socket_path}.",
        )

    def _unlink_socket_path(self) -> None:
        try:
            if self.socket_path.exists() and stat.S_ISSOCK(self.socket_path.stat().st_mode):
                self.socket_path.unlink()
        except FileNotFoundError:
            return


def request_control(
    socket_path: Path,
    command: str,
    *,
    timeout_seconds: float = DEFAULT_CONTROL_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Send a synchronous control request and return the JSON response."""

    payload = json.dumps({"command": command}, sort_keys=True).encode("utf-8") + b"\n"
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(timeout_seconds)
            client.connect(str(socket_path))
            client.sendall(payload)
            chunks: list[bytes] = []
            while True:
                chunk = client.recv(4096)
                if not chunk:
                    break
                chunks.append(chunk)
                if b"\n" in chunk:
                    break
    except (ConnectionRefusedError, FileNotFoundError, TimeoutError, OSError) as exc:
        raise SocketUnavailableError(f"Control socket unavailable at {socket_path}: {exc}") from exc

    raw_response = b"".join(chunks).strip()
    if not raw_response:
        raise ControlSocketError(f"Control socket {socket_path} returned no response.")

    try:
        response = json.loads(raw_response.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ControlSocketError(f"Control socket returned invalid JSON: {exc}") from exc

    if not isinstance(response, dict):
        raise ControlSocketError("Control socket response must be a JSON object.")
    return response