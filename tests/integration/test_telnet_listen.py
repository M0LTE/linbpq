"""Phase 3 deferral — LISTEN / CQ / UNPROTO with no AX.25 port.

Our test config has only Telnet and AX/IP-UDP ports, neither of which
is an AX.25 RF port.  Each of these commands has a recognisable
not-applicable response in that environment; lock those in.
"""

from __future__ import annotations

from helpers.telnet_client import TelnetClient


def test_listen_alone_disables_listening(linbpq):
    """``LISTEN`` with no port number turns listening off."""
    with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
        client.login("test", "test")
        response = client.run_command("LISTEN")
    assert b"Listening disabled" in response, (
        f"LISTEN bare did not disable listening: {response!r}"
    )


def test_listen_on_non_ax25_port_is_rejected(linbpq):
    """LISTEN <port> on a Telnet/AXIP port reports it isn't AX.25."""
    with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
        client.login("test", "test")
        response = client.run_command("LISTEN 1")
    assert b"not an ax.25 port" in response, (
        f"LISTEN 1 unexpected response: {response!r}"
    )


def test_cq_without_listen_is_rejected(linbpq):
    with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
        client.login("test", "test")
        response = client.run_command("CQ")
    assert b"You must enter LISTEN before calling CQ" in response, (
        f"CQ without LISTEN unexpected response: {response!r}"
    )


def test_unproto_with_no_destination_is_rejected(linbpq):
    with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
        client.login("test", "test")
        response = client.run_command("UNPROTO 1")
    assert b"Destination missing" in response, (
        f"UNPROTO 1 unexpected response: {response!r}"
    )
