"""Phase 3 — BYE behaviour.

Empirically, ``BYE`` is *not* a logout: it prints
``Disconnected from Node - Telnet Session kept`` and the underlying
telnet session continues to accept commands.  Its primary job is to
disconnect from a sub-session entered via ``CONNECT``; from the bare
node prompt it just emits the message.

To fully close, the client closes the TCP socket.  Lock both halves
of this in.
"""

from __future__ import annotations

from helpers.telnet_client import TelnetClient


def test_bye_emits_disconnect_message(linbpq):
    with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
        client.login("test", "test")
        response = client.run_command("BYE", idle_timeout=1.0)
    assert b"Disconnected" in response, (
        f"BYE did not produce disconnect message: {response!r}"
    )
    assert b"Telnet Session kept" in response, (
        f"expected 'Telnet Session kept' marker: {response!r}"
    )


def test_node_session_continues_after_bye(linbpq):
    """After BYE the telnet session stays usable; commands still work."""
    with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
        client.login("test", "test")
        client.run_command("BYE", idle_timeout=1.0)
        response = client.run_command("PORTS")
    assert b"TEST:N0CALL}" in response, (
        f"node session not still alive after BYE: {response!r}"
    )
    assert b"Telnet" in response, f"PORTS did not run: {response!r}"
