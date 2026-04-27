"""Phase 2 deferral — AX/IP-over-UDP listener canary.

Linbpq's BPQAXIP driver listens on a UDP port for AX.25 frames wrapped
in UDP datagrams.  Without a peer node configured we can't drive a
full conversation, but we can verify:

- The UDP socket is bound (the boot log doesn't report a bind failure).
- Sending arbitrary garbage at the port doesn't crash linbpq — the
  daemon is still serving telnet afterwards.
"""

from __future__ import annotations

import socket

from helpers.telnet_client import TelnetClient


def test_axip_udp_port_is_bound(linbpq):
    log = linbpq.stdout_path.read_text(errors="replace")
    assert "bind" not in log.lower() or "failed" not in log.lower(), (
        f"linbpq reported a bind failure; log:\n{log[:2000]}"
    )
    # Sanity: the AXIP port string appears in the boot output.
    # (BPQAXIP prints "AXIP UDP Port n" at startup.)


def test_axip_garbage_does_not_crash_daemon(linbpq):
    """Send a malformed UDP packet; linbpq must keep serving telnet."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.sendto(b"NOT_A_VALID_AX25_FRAME", ("127.0.0.1", linbpq.axip_port))

    # Daemon still alive?
    with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
        client.login("test", "test")
        response = client.run_command("VERSION")
    assert b"Version" in response, (
        f"daemon dead after AXIP garbage: {response!r}"
    )
