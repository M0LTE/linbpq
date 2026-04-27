"""Fake VARA TNC simulator.

VARA is a TCP-attached HF modem.  linbpq dials OUT to the VARA TNC on
two adjacent TCP ports — the *control* socket on the configured port
and the *data* socket on ``port + 1``.  Once both connect, linbpq
waits ~1s then sends an INIT script (``MYCALL N0CALL\\r`` then
``LISTEN ON\\r`` plus any keywords the cfg block accumulated).  See
``VARA.c`` ``VARAThread`` and ``VARAExtInit`` for the wire flow.

This helper picks a pair of adjacent free ports, stands up two TCP
listeners, and exposes the bytes linbpq wrote to each socket for
test inspection.

Pattern mirrors :class:`helpers.cmdport_app.CmdportApp` and
:class:`helpers.kiss_tcp_server.KissTcpServer`.
"""

from __future__ import annotations

import socket
import threading
import time
from contextlib import contextmanager


def _pick_adjacent_ports(max_attempts: int = 50) -> tuple[int, int]:
    """Find ``(p, p+1)`` where both are free on loopback.

    The kernel's ephemeral allocation isn't guaranteed to give us
    consecutive ports, so we probe and retry.  Cheap on loopback.
    """
    for _ in range(max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s1:
            s1.bind(("127.0.0.1", 0))
            p = s1.getsockname()[1]
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s2:
                s2.bind(("127.0.0.1", p + 1))
        except OSError:
            continue
        return p, p + 1
    raise RuntimeError("could not allocate adjacent loopback ports")


class VaraModem:
    """Two TCP listeners standing in for VARA's control + data sockets."""

    def __init__(self) -> None:
        self.control_port, self.data_port = _pick_adjacent_ports()

        self._ctrl_sock = self._listen(self.control_port)
        self._data_sock = self._listen(self.data_port)

        self._ctrl_client: socket.socket | None = None
        self._data_client: socket.socket | None = None
        self._ctrl_received = bytearray()
        self._data_received = bytearray()
        self._lock = threading.Lock()
        self._stop = threading.Event()

        self._ctrl_thread = threading.Thread(
            target=self._serve, args=(self._ctrl_sock, "ctrl"), daemon=True
        )
        self._data_thread = threading.Thread(
            target=self._serve, args=(self._data_sock, "data"), daemon=True
        )
        self._ctrl_thread.start()
        self._data_thread.start()

    @staticmethod
    def _listen(port: int) -> socket.socket:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.0.1", port))
        s.listen(1)
        return s

    def _serve(self, listener: socket.socket, which: str) -> None:
        listener.settimeout(0.5)
        while not self._stop.is_set():
            try:
                client, _ = listener.accept()
            except (socket.timeout, TimeoutError):
                continue
            except OSError:
                return
            client.settimeout(0.5)
            with self._lock:
                if which == "ctrl":
                    self._ctrl_client = client
                else:
                    self._data_client = client
            buf = self._ctrl_received if which == "ctrl" else self._data_received
            while not self._stop.is_set():
                try:
                    chunk = client.recv(4096)
                except (TimeoutError, socket.timeout):
                    continue
                except OSError:
                    return
                if not chunk:
                    return
                with self._lock:
                    buf.extend(chunk)

    def wait_for_both_connected(self, timeout: float = 10.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                if self._ctrl_client is not None and self._data_client is not None:
                    return True
            time.sleep(0.05)
        return False

    def control_received(self) -> bytes:
        with self._lock:
            return bytes(self._ctrl_received)

    def data_received(self) -> bytes:
        with self._lock:
            return bytes(self._data_received)

    def wait_for_control_data(self, marker: bytes, timeout: float = 10.0) -> bytes:
        """Spin until ``marker`` appears in the control-socket bytes."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            buf = self.control_received()
            if marker in buf:
                return buf
            time.sleep(0.05)
        return self.control_received()

    def send_control(self, data: bytes) -> None:
        with self._lock:
            client = self._ctrl_client
        if client is None:
            raise RuntimeError("control socket not connected")
        client.sendall(data)

    def close(self) -> None:
        self._stop.set()
        for s in (
            self._ctrl_client,
            self._data_client,
            self._ctrl_sock,
            self._data_sock,
        ):
            try:
                if s is not None:
                    s.close()
            except OSError:
                pass
        self._ctrl_thread.join(timeout=1.0)
        self._data_thread.join(timeout=1.0)


@contextmanager
def vara_modem():
    m = VaraModem()
    try:
        yield m
    finally:
        m.close()
