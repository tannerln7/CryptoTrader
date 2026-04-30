from __future__ import annotations

import socket

from market_recorder.systemd_notify import notify_ready


def test_notify_ready_writes_to_notify_socket(tmp_path, monkeypatch) -> None:
    notify_path = tmp_path / "notify.sock"
    with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as server:
        server.bind(str(notify_path))
        monkeypatch.setenv("NOTIFY_SOCKET", str(notify_path))

        assert notify_ready(status="Recorder service is running.") is True

        payload = server.recv(1024).decode("utf-8")

    assert "READY=1" in payload
    assert "STATUS=Recorder service is running." in payload