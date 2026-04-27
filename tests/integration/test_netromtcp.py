"""NET/ROM-over-TCP listener — protocol-level coverage.

Beyond the listener-bind canary in ``test_aux_listeners.py``: drive
real frames at ``NETROMPORT`` and verify linbpq's per-frame protocol
behaviour.

Wire format (NETROMTCP.c:27):

    Length(2 LE) | Call(10 ASCII) | PID(1 = 0xCF) | NETROM L3/L4 packet

linbpq processes the first frame on each TCP connection through the
``FindNeighbour`` gate (NETROMTCP.c:472): the inbound call must match
a configured ``ROUTES:`` entry on the same port number that the
``Telnet`` PORT block carries (since ``NETROMPORT`` rides under the
telnet driver — TelnetPoll passes its BPQ-port-number to
``checkNRTCPSockets``).

Coverage:

- Unknown call → linbpq closes the socket (NETROMTCP.c:500).
- Known call → connection accepted; ``ROUTES`` output for that
  neighbour gains the leading ``>`` active-link marker (Cmd.c:1912
  — set when ``NEIGHBOUR_LINK->L2STATE >= 5``).

The L3 payload we send is a TTL=1 drop frame: linbpq decrements TTL
to 0 and releases the buffer (L4Code.c:188), so we exercise the
listener without provoking actual NET/ROM-routing side effects.
"""

from __future__ import annotations

import socket
import time
from pathlib import Path
from string import Template

import pytest

from helpers.linbpq_instance import LinbpqInstance
from helpers.netromtcp import build_l3_drop_packet, build_nrtcp_frame
from helpers.telnet_client import TelnetClient


_NETROMTCP_CFG = Template(
    """\
SIMPLE=1
NODECALL=N0CALL
NODEALIAS=TEST
LOCATOR=NONE

PORT
 PORTNUM=1
 ID=Telnet
 DRIVER=Telnet
 CONFIG
 TCPPORT=$telnet_port
 HTTPPORT=$http_port
 NETROMPORT=$netrom_port
 MAXSESSIONS=10
 USER=test,test,N0CALL,,SYSOP
ENDPORT

ROUTES:
N0FAKE,200,1
***
"""
)


def _recv_until_eof(sock: socket.socket, timeout: float) -> bytes:
    """Read from ``sock`` until peer closes (recv returns 0) or
    ``timeout`` elapses.  Returns whatever was received."""
    sock.settimeout(timeout)
    out = bytearray()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            chunk = sock.recv(4096)
        except socket.timeout:
            break
        except (ConnectionResetError, OSError):
            break
        if not chunk:
            return bytes(out)
        out.extend(chunk)
    return bytes(out)


def _peer_closed(sock: socket.socket) -> bool:
    """Probe whether ``sock`` has been closed by the peer.  Tries a
    short-timeout recv; an empty read or connection-reset means
    closed.  ``socket.timeout`` (an ``OSError`` subclass on
    Python 3.10+) means the socket is open but idle — return False."""
    sock.settimeout(0.5)
    try:
        chunk = sock.recv(1)
    except socket.timeout:
        return False
    except (ConnectionResetError, OSError):
        return True
    return chunk == b""


def test_netromtcp_unknown_call_closes_connection(tmp_path: Path):
    """First frame's call doesn't match any configured ROUTES entry —
    linbpq closes the socket (NETROMTCP.c:500: ``Neighbour ... not
    found - closing connection``)."""
    with LinbpqInstance(tmp_path, config_template=_NETROMTCP_CFG) as linbpq:
        sock = socket.create_connection(
            ("127.0.0.1", linbpq.netrom_port), timeout=5.0
        )
        try:
            frame = build_nrtcp_frame("N0OTHER", build_l3_drop_packet())
            sock.sendall(frame)
            # linbpq should close the socket promptly.
            data = _recv_until_eof(sock, timeout=3.0)
            assert data == b"", (
                f"expected immediate EOF, got {len(data)} bytes: {data!r}"
            )
            # Confirm second probe also reports closed.
            assert _peer_closed(sock), (
                "socket should be closed after unknown-call rejection"
            )
        finally:
            sock.close()


def test_netromtcp_known_call_marks_route_active(tmp_path: Path):
    """First frame's call matches a configured ROUTES entry — linbpq
    accepts the connection and marks the route's NEIGHBOUR_LINK as
    L2STATE >= 5, visible in ``ROUTES`` output as a leading ``>``
    on that neighbour's row (Cmd.c:1912)."""
    with LinbpqInstance(tmp_path, config_template=_NETROMTCP_CFG) as linbpq:
        # First confirm: route configured but not yet active — no `>`.
        with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
            client.login("test", "test")
            before = client.run_command("ROUTES")
        assert b"N0FAKE" in before, (
            f"static route N0FAKE missing from ROUTES: {before!r}"
        )
        # The active marker `>` shouldn't be on N0FAKE's line yet.
        for line in before.splitlines():
            if b"N0FAKE" in line:
                assert not line.lstrip().startswith(b">"), (
                    f"N0FAKE marked active before TCP connect: {line!r}"
                )

        # Open the NET/ROM TCP socket and identify ourselves as N0FAKE.
        sock = socket.create_connection(
            ("127.0.0.1", linbpq.netrom_port), timeout=5.0
        )
        try:
            frame = build_nrtcp_frame("N0FAKE", build_l3_drop_packet())
            sock.sendall(frame)
            # Give linbpq's poll loop a moment to process.
            time.sleep(1.5)
            # Socket should still be alive.
            assert not _peer_closed(sock), (
                "socket closed after known-call connect — should be live"
            )

            with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
                client.login("test", "test")
                after = client.run_command("ROUTES")
        finally:
            sock.close()

    # Expect the active-link marker on the N0FAKE row.
    n0fake_line = next(
        (l for l in after.splitlines() if b"N0FAKE" in l), b""
    )
    assert n0fake_line, f"N0FAKE missing from ROUTES after connect: {after!r}"
    assert b">" in n0fake_line.split(b"N0FAKE")[0], (
        f"N0FAKE row missing active-link `>` marker: {n0fake_line!r}"
    )
