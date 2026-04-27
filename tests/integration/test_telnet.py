"""Phase 2 — Telnet console: login flow and a node-prompt command."""

from __future__ import annotations

from helpers.telnet_client import TelnetClient


def test_telnet_login_then_ports_command(linbpq):
    """Authenticate as the test user, send PORTS, expect the listing."""
    with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
        client.login("test", "test")
        client.write_line("PORTS")
        response = client.read_idle()
    # BPQ emits ``ALIAS:CALL}`` as the per-command prompt prefix.
    assert b"TEST:N0CALL}" in response, f"no prompt prefix: {response!r}"
    assert b"Ports" in response, f"no Ports heading: {response!r}"
    # The Telnet driver port we configured should be in the listing.
    assert b"Telnet" in response, f"telnet port not listed: {response!r}"


def test_telnet_invalid_password_is_rejected(linbpq):
    """Wrong password must not yield the ``Connected to … Telnet Server``
    welcome banner or the post-login prompt prefix."""
    with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
        client.read_until(b"user:")
        client.write_line("test")
        client.read_until(b"password:")
        client.write_line("definitely-not-the-password")
        response = client.read_idle(idle_timeout=0.5, max_total=2.0)
    assert b"Telnet Server" not in response, (
        f"login welcome leaked after bad password: {response!r}"
    )
    assert b"TEST:N0CALL}" not in response, (
        f"prompt prefix leaked after bad password: {response!r}"
    )
