"""A fake TCP "application" linbpq dials out to via CMDPORT.

When a sysop runs ``C <bpqport> HOST <n>`` from a node session,
linbpq opens a TCP connection to ``127.0.0.1:CMDPort[n]`` and
relays everything between the user and the app.  This helper
stands up a TCP listener that accepts one such outbound
connection, captures what linbpq sends, and exposes a way to
send back.

Used by ``test_cmdport.py``.  Pattern mirrors
``helpers.kiss_tcp_server.KissTcpServer``.
"""

from __future__ import annotations

import socket
import threading
from contextlib import contextmanager


class CmdportApp:
    """Bind ``127.0.0.1:<auto>``, accept one TCP connection."""

    def __init__(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(1)
        self.port: int = self._sock.getsockname()[1]

        self._accept_event = threading.Event()
        self._client: socket.socket | None = None
        self._stop = threading.Event()

        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        self._sock.settimeout(0.5)
        while not self._stop.is_set():
            try:
                client, _ = self._sock.accept()
            except (socket.timeout, TimeoutError):
                continue
            except OSError:
                return
            self._client = client
            self._accept_event.set()
            return

    def wait_for_client(self, timeout: float = 5.0) -> bool:
        return self._accept_event.wait(timeout)

    def recv(self, max_bytes: int = 4096, timeout: float = 2.0) -> bytes:
        if self._client is None:
            raise RuntimeError("no client connected")
        self._client.settimeout(timeout)
        try:
            return self._client.recv(max_bytes)
        except (TimeoutError, socket.timeout):
            return b""

    def recv_until(self, marker: bytes, timeout: float = 2.0) -> bytes:
        """Read until ``marker`` appears or the deadline passes."""
        import time

        if self._client is None:
            raise RuntimeError("no client connected")
        deadline = time.monotonic() + timeout
        buf = b""
        while time.monotonic() < deadline and marker not in buf:
            self._client.settimeout(min(0.4, max(0.01, deadline - time.monotonic())))
            try:
                chunk = self._client.recv(4096)
            except (TimeoutError, socket.timeout):
                continue
            if not chunk:
                break
            buf += chunk
        return buf

    def send(self, data: bytes) -> None:
        if self._client is None:
            raise RuntimeError("no client connected")
        self._client.sendall(data)

    def close(self) -> None:
        self._stop.set()
        for s in (self._client, self._sock):
            try:
                if s is not None:
                    s.close()
            except OSError:
                pass
        self._thread.join(timeout=1.0)


@contextmanager
def cmdport_app():
    app = CmdportApp()
    try:
        yield app
    finally:
        app.close()
