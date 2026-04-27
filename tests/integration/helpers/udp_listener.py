"""Tiny UDP recording listener.

Used by the HSMODEM driver test.  HSMODEM is a UDP-attached modem
(``HSMODEM.c``) — linbpq sends polls *to* ``port`` (the HSMODEM
command port) and binds *itself* to ``port + 2`` to receive.

This helper takes the role of HSMODEM's command port: it binds
``127.0.0.1:<port>`` and records every datagram linbpq writes there.
"""

from __future__ import annotations

import socket
import threading
import time
from contextlib import contextmanager


class UdpListener:
    """Bind ``127.0.0.1:<auto>`` UDP, record datagrams."""

    def __init__(self) -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.settimeout(0.3)
        self.port: int = self._sock.getsockname()[1]

        self.datagrams: list[bytes] = []
        self._lock = threading.Lock()
        self._stop = threading.Event()

        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                data, _addr = self._sock.recvfrom(65536)
            except (TimeoutError, socket.timeout):
                continue
            except OSError:
                return
            with self._lock:
                self.datagrams.append(data)

    def wait_for_datagram(self, timeout: float = 10.0) -> bytes | None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                if self.datagrams:
                    return self.datagrams[0]
            time.sleep(0.05)
        return None

    def close(self) -> None:
        self._stop.set()
        try:
            self._sock.close()
        except OSError:
            pass
        self._thread.join(timeout=1.0)


@contextmanager
def udp_listener():
    listener = UdpListener()
    try:
        yield listener
    finally:
        listener.close()
