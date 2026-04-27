"""Phase 1 smoke tests — does the daemon stand up, do its sockets answer."""

from __future__ import annotations

import socket


def test_telnet_port_accepts_connections(linbpq):
    """linbpq starts cleanly and the Telnet server greets new connections."""
    import time

    with socket.create_connection(
        ("127.0.0.1", linbpq.telnet_port), timeout=2
    ) as sock:
        sock.settimeout(0.5)
        data = b""
        deadline = time.monotonic() + 3.0
        # The Telnet server sends IAC negotiation bytes (FF FB ...)
        # followed by a "user:" prompt; on a busy CI run the two halves
        # can arrive in separate TCP segments, so accumulate until we
        # see the marker or the deadline expires.
        while b"user:" not in data and time.monotonic() < deadline:
            try:
                chunk = sock.recv(256)
            except (TimeoutError, socket.timeout):
                continue
            if not chunk:
                break
            data += chunk
    assert b"user:" in data, f"expected login prompt, got {data!r}"


def test_http_port_accepts_connections(linbpq):
    """The HTTP admin port is reachable and answers GET / with an HTTP response."""
    with socket.create_connection(
        ("127.0.0.1", linbpq.http_port), timeout=2
    ) as sock:
        sock.sendall(b"GET / HTTP/1.0\r\n\r\n")
        sock.settimeout(2)
        # linbpq keeps the connection open after responding; just grab the
        # first chunk and look at the status line.
        data = sock.recv(4096)
    assert data.startswith(b"HTTP/"), f"expected HTTP response, got {data[:80]!r}"
    assert b"200" in data.split(b"\r\n", 1)[0], f"non-200 status: {data[:80]!r}"
