"""Minimal direct systemd notify protocol support without external dependencies."""

from __future__ import annotations

import os
import socket


def notify(message: str) -> bool:
    """Send a datagram to ``NOTIFY_SOCKET`` when present."""

    notify_socket = os.environ.get("NOTIFY_SOCKET")
    if not notify_socket:
        return False

    if not message:
        raise ValueError("systemd notify messages must be non-empty")

    target = notify_socket
    if target.startswith("@"):
        target = "\0" + target[1:]
    if not target.startswith("/") and not target.startswith("\0"):
        raise OSError(f"Unsupported NOTIFY_SOCKET value: {notify_socket!r}")

    with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as client:
        client.connect(target)
        client.sendall(message.encode("utf-8"))
    return True


def notify_ready(*, status: str | None = None) -> bool:
    parts = ["READY=1"]
    if status:
        parts.append(f"STATUS={status}")
    return notify("\n".join(parts))


def notify_status(status: str) -> bool:
    return notify(f"STATUS={status}")


def notify_stopping(*, status: str | None = None) -> bool:
    parts = ["STOPPING=1"]
    if status:
        parts.append(f"STATUS={status}")
    return notify("\n".join(parts))