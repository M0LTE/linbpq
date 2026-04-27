"""Minimal telnet client for integration tests.

Just enough of RFC 854 to talk to linbpq's telnet console: it strips IAC
negotiation, can send a complete login flow (user/password) and read until
a known prompt appears.  Not a general-purpose telnet implementation.
"""

from __future__ import annotations

import socket
import time

IAC = 0xFF
DONT = 0xFE
DO = 0xFD
WONT = 0xFC
WILL = 0xFB


def _strip_iac(buf: bytes) -> bytes:
    """Remove IAC negotiation triplets and isolated IACs from ``buf``."""
    out = bytearray()
    i = 0
    while i < len(buf):
        b = buf[i]
        if b == IAC:
            if i + 2 < len(buf) and buf[i + 1] in (DO, DONT, WILL, WONT):
                i += 3
                continue
            i += 1
            continue
        out.append(b)
        i += 1
    return bytes(out)


class TelnetClient:
    def __init__(self, host: str, port: int, timeout: float = 3.0):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.sock.settimeout(timeout)
        self._buf = b""

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass

    def __enter__(self) -> "TelnetClient":
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    def read_until(self, marker: bytes, timeout: float = 3.0) -> bytes:
        """Read (with IAC stripped) until ``marker`` appears, or timeout."""
        deadline = time.monotonic() + timeout
        while marker not in self._buf:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(
                    f"never saw {marker!r}; got {self._buf!r}"
                )
            self.sock.settimeout(remaining)
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError(
                    f"connection closed before seeing {marker!r}; "
                    f"got {self._buf!r}"
                )
            self._buf += _strip_iac(chunk)
        idx = self._buf.index(marker) + len(marker)
        out, self._buf = self._buf[:idx], self._buf[idx:]
        return out

    def read_idle(self, idle_timeout: float = 0.5, max_total: float = 5.0) -> bytes:
        """Read until the server stops sending for ``idle_timeout`` seconds.

        BPQ's telnet console emits a per-command prompt ``ALIAS:CALL}`` at
        the *start* of each response and no trailing prompt — there is no
        sentinel byte to read up to.  Idle-detection is the only honest
        way to mark end-of-response.
        """
        deadline = time.monotonic() + max_total
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            self.sock.settimeout(min(idle_timeout, remaining))
            try:
                chunk = self.sock.recv(4096)
            except (TimeoutError, socket.timeout):
                break
            if not chunk:
                break
            self._buf += _strip_iac(chunk)
        out, self._buf = self._buf, b""
        return out

    def write_line(self, text: str) -> None:
        self.sock.sendall(text.encode("ascii") + b"\r")

    def login(self, user: str, password: str) -> bytes:
        """Drive the user/password prompts; return up to and including the
        ``Connected to ... Telnet Server\\r\\n\\r\\n`` welcome banner that
        marks a successful login."""
        self.read_until(b"user:")
        self.write_line(user)
        self.read_until(b"password:")
        self.write_line(password)
        return self.read_until(b"Telnet Server\r\n\r\n")
