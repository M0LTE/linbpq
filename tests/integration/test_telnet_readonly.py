"""Phase 3 — read-only commands that work for any authenticated user.

Each row asserts that running ``cmd`` returns a non-error response and
that, where ``contains`` is non-empty, the response contains the marker
string.  The marker is intentionally narrow — just enough to prove the
command did the thing it claims to do, not so wide that we lock in
formatting that may legitimately drift.
"""

from __future__ import annotations

import pytest

from helpers.telnet_client import TelnetClient

# (command, expected substring or None for "any non-error response")
READONLY_COMMANDS = [
    pytest.param("VERSION", b"Version", id="VERSION"),
    pytest.param("INFO", None, id="INFO"),
    pytest.param("NODES", b"Nodes", id="NODES"),
    pytest.param("ROUTES", b"Routes", id="ROUTES"),
    pytest.param("LINKS", b"Links", id="LINKS"),
    pytest.param("USERS", b"G8BPQ Network System", id="USERS"),
    pytest.param("STATS", b"Uptime", id="STATS"),
    # MHEARD without a port number prints usage hint — that's still a
    # well-formed response, not an error.
    pytest.param("MHEARD", b"Port Number needed", id="MHEARD-no-port"),
    pytest.param("?", b"CONNECT", id="HELP-?"),
    # STREAMS is reachable for a regular logged-in user despite the
    # AI-generated command doc tagging it sysop.  See empirical probe
    # results in the Phase 3 commit message.
    pytest.param("STREAMS", b"|", id="STREAMS"),
]


@pytest.mark.parametrize("cmd, contains", READONLY_COMMANDS)
def test_telnet_readonly_command(linbpq, cmd, contains):
    with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
        client.login("test", "test")
        response = client.run_command(cmd)
    # Every command response is prefixed with the node prompt token.
    assert b"TEST:N0CALL}" in response, (
        f"{cmd}: no prompt prefix; got {response!r}"
    )
    assert b"Invalid command" not in response, (
        f"{cmd}: linbpq rejected as invalid; got {response!r}"
    )
    if contains is not None:
        assert contains in response, (
            f"{cmd}: expected {contains!r} in response; got {response!r}"
        )
