"""Fake FLDigi/FLARQ TNC simulator.

Differs from VARA/ARDOP: FLDigi's two TCP ports are *not* adjacent.
``ADDR <ip> <port>`` configures the *ARQ* port (default 7322); the
XML-RPC control port is at ``port + 40`` (default 7362).  See
``FLDigi.c`` ``ProcessLine`` lines 1418-1421.

linbpq dials the control socket first, then the data socket.  Once
both are up, an XML-RPC poll fires every second and produces
visible ``POST /RPC2 HTTP/1.1`` traffic on the control socket — a
recognisable signature for tests.
"""

from __future__ import annotations

import socket
import threading
import time
from contextlib import contextmanager


def _pick_pair_with_offset(offset: int, max_attempts: int = 50) -> tuple[int, int]:
    """Find ``(p, p + offset)`` where both are free on loopback."""
    for _ in range(max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s1:
            s1.bind(("127.0.0.1", 0))
            p = s1.getsockname()[1]
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s2:
                s2.bind(("127.0.0.1", p + offset))
        except OSError:
            continue
        return p, p + offset
    raise RuntimeError(f"could not allocate ports with +{offset} offset")


class FldigiModem:
    """Two TCP listeners standing in for FLDigi's ARQ + XML-RPC sockets."""

    def __init__(self) -> None:
        self.arq_port, self.xml_port = _pick_pair_with_offset(40)

        self._arq_sock = self._listen(self.arq_port)
        self._xml_sock = self._listen(self.xml_port)

        self._arq_client: socket.socket | None = None
        self._xml_client: socket.socket | None = None
        self._arq_received = bytearray()
        self._xml_received = bytearray()
        self._lock = threading.Lock()
        self._stop = threading.Event()

        self._arq_thread = threading.Thread(
            target=self._serve, args=(self._arq_sock, "arq"), daemon=True
        )
        self._xml_thread = threading.Thread(
            target=self._serve, args=(self._xml_sock, "xml"), daemon=True
        )
        self._arq_thread.start()
        self._xml_thread.start()

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
                if which == "arq":
                    self._arq_client = client
                else:
                    self._xml_client = client
            buf = self._arq_received if which == "arq" else self._xml_received
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

    def wait_for_both_connected(self, timeout: float = 15.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                if self._arq_client is not None and self._xml_client is not None:
                    return True
            time.sleep(0.05)
        return False

    def xml_received(self) -> bytes:
        with self._lock:
            return bytes(self._xml_received)

    def wait_for_xml_data(self, marker: bytes, timeout: float = 15.0) -> bytes:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            buf = self.xml_received()
            if marker in buf:
                return buf
            time.sleep(0.05)
        return self.xml_received()

    def close(self) -> None:
        self._stop.set()
        for s in (
            self._arq_client,
            self._xml_client,
            self._arq_sock,
            self._xml_sock,
        ):
            try:
                if s is not None:
                    s.close()
            except OSError:
                pass
        self._arq_thread.join(timeout=1.0)
        self._xml_thread.join(timeout=1.0)


@contextmanager
def fldigi_modem():
    m = FldigiModem()
    try:
        yield m
    finally:
        m.close()
