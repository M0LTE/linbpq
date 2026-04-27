"""A minimal KISS-over-TCP server fixture for tests.

linbpq's ``TYPE=ASYNC PROTOCOL=KISS IPADDR TCPPORT`` configuration is
the way it talks to remote KISS modems / softmodems (e.g. Direwolf,
UZ7HO, kissproxy).  This helper stands up a tiny TCP listener that
accepts one client and records connection state, just enough to
verify linbpq connects out as expected without depending on a real
softmodem.

Inspired by m0lte/kissproxy (the actual production peer linbpq
typically connects to).
"""

from __future__ import annotations

import socket
import threading
from contextlib import contextmanager


class KissTcpServer:
    """Bind ``127.0.0.1:<chosen port>`` and accept one TCP connection.

    The accept loop runs on a background thread.  ``wait_for_client``
    blocks until linbpq connects (or the timeout expires).
    """

    def __init__(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(1)
        self.port: int = self._sock.getsockname()[1]
        self._client_event = threading.Event()
        self._client_sock: socket.socket | None = None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        self._sock.settimeout(0.5)
        while not self._stop.is_set():
            try:
                client, _addr = self._sock.accept()
            except (socket.timeout, TimeoutError):
                continue
            except OSError:
                return
            self._client_sock = client
            self._client_event.set()
            return

    def wait_for_client(self, timeout: float = 5.0) -> bool:
        return self._client_event.wait(timeout)

    def close(self) -> None:
        self._stop.set()
        try:
            self._sock.close()
        except OSError:
            pass
        if self._client_sock is not None:
            try:
                self._client_sock.close()
            except OSError:
                pass
        self._thread.join(timeout=1.0)


@contextmanager
def kiss_tcp_server():
    server = KissTcpServer()
    try:
        yield server
    finally:
        server.close()
