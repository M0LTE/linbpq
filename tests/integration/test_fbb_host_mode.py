"""FBB host-mode protocol over ``FBBPORT``.

linbpq's FBB-mode TCP listener is a binary-relay variant of the
telnet console.  It's used by clients like BPQTermTCP, RMS Express,
paclink, etc. — anything that wants to ride the BPQ host-mode link
over TCP.

Differences from the telnet listener (``TCPPORT``):

- **No IAC negotiation, no visible prompts** during the login
  exchange.  The client supplies ``<user>\\r`` then ``<pass>\\r``
  blind and a successful login leaves the connection open.
- **Bare ``\\r`` line terminators** (telnet uses CRLF or IAC).
- A bad password emits the literal ``password:`` text and keeps
  asking.

This is *not* the full FBB SID/proposal protocol from
[packethacking/ax25spec/doc/fbb-forwarding-protocol.md] — that
protocol is what a forwarding *partner* speaks once it has
connected; the listener here is the lower-level transport.

Source: ``TelnetV6.c::DataSocket_ReadFBB`` (around line 4487).
"""

from __future__ import annotations

import socket
import time


def _read_until_idle(sock: socket.socket, timeout: float = 1.5) -> bytes:
    """Read until the server stops sending for ``timeout`` seconds."""
    deadline = time.monotonic() + timeout
    buf = b""
    sock.settimeout(0.4)
    while time.monotonic() < deadline:
        try:
            chunk = sock.recv(4096)
        except (TimeoutError, socket.timeout):
            break
        if not chunk:
            break
        buf += chunk
    return buf


def test_fbb_login_then_command_runs(linbpq):
    """Bare ``user\\r`` + ``pass\\r`` followed by a command line
    runs against the node and returns the prompt-prefixed output."""
    with socket.create_connection(
        ("127.0.0.1", linbpq.fbb_port), timeout=3
    ) as sock:
        # FBB login is silent — no banner, no prompts.
        sock.sendall(b"test\r")
        time.sleep(0.2)
        sock.sendall(b"test\r")
        time.sleep(0.5)
        # Drain anything that may have arrived (should be nothing).
        _read_until_idle(sock, timeout=0.5)

        sock.sendall(b"PORTS\r")
        time.sleep(0.3)
        response = _read_until_idle(sock, timeout=1.0)

    assert b"TEST:N0CALL}" in response, (
        f"no prompt prefix on FBB session: {response!r}"
    )
    assert b"Telnet" in response, f"PORTS output missing port: {response!r}"


def test_fbb_bad_password_reissues_prompt(linbpq):
    """A bad password leaves the connection in the password-asking
    state — the literal ``password:`` text appears in the response."""
    with socket.create_connection(
        ("127.0.0.1", linbpq.fbb_port), timeout=3
    ) as sock:
        sock.sendall(b"test\r")
        time.sleep(0.2)
        sock.sendall(b"definitely-not-the-password\r")
        time.sleep(0.5)
        response = _read_until_idle(sock, timeout=1.5)

    assert b"password:" in response, (
        f"FBB didn't re-prompt after bad password: {response!r}"
    )
    # And the node prompt definitely does not appear.
    assert b"TEST:N0CALL}" not in response, (
        f"node prompt leaked after bad password: {response!r}"
    )


def test_fbb_initial_silence(linbpq):
    """A fresh FBB connection sends nothing until the client speaks
    first (no IAC negotiation, no prompt banner)."""
    with socket.create_connection(
        ("127.0.0.1", linbpq.fbb_port), timeout=3
    ) as sock:
        # Read for ~1s without sending anything.
        sock.settimeout(1.0)
        try:
            data = sock.recv(256)
        except (TimeoutError, socket.timeout):
            data = b""
    assert data == b"", (
        f"FBB sent unexpected pre-login data: {data!r}"
    )
