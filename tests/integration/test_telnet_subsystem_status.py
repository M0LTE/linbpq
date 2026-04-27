"""Phase 3 deferral — subsystem-status commands.

TELSTATUS and AGWSTATUS report on their respective subsystems.  With
no port number argument, TELSTATUS reports "Invalid Port".  AGWSTATUS
reports "AGW Interface is not enabled" — interesting, given our
config has ``AGWPORT=...``; that suggests the status command tracks a
different "enabled" flag than the port-listening code.  Lock the
current observable behaviour in so refactors that change it are
visible.
"""

from __future__ import annotations

from helpers.telnet_client import TelnetClient


def test_telstatus_without_port_is_rejected(linbpq):
    with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
        client.login("test", "test")
        response = client.run_command("TELSTATUS")
    assert b"Invalid Port" in response, (
        f"TELSTATUS without port unexpected: {response!r}"
    )


def test_agwstatus_reports_state(linbpq):
    """AGWSTATUS prints the AGW sockets table when AGW is enabled
    (our config sets ``AGWPORT=...``).  We assert on the recognisable
    column header rather than a fragile substring."""
    with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
        client.login("test", "test")
        response = client.run_command("AGWSTATUS")
    assert b"Sockets" in response and b"Stream" in response, (
        f"AGWSTATUS sockets table missing: {response!r}"
    )
    assert b"Invalid command" not in response
