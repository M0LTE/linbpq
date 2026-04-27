"""Phase 3 deferral — IP-gateway commands without the IP gateway.

Without the IP gateway feature configured, PING / ARP / IPROUTE all
report "IP Gateway is not enabled" rather than crashing or running
unexpectedly.  NRR (NET/ROM Record Route) reports "Not found" when no
NET/ROM route exists, which is true with our config.

Lock these in so an accidental partial-wiring of the IP gateway (e.g.
half-broken code path that silently no-ops) lands a test red.
"""

from __future__ import annotations

import pytest

from helpers.telnet_client import TelnetClient

GATEWAY_DISABLED = b"IP Gateway is not enabled"


@pytest.mark.parametrize(
    "cmd, expected",
    [
        pytest.param("PING 1.1.1.1", GATEWAY_DISABLED, id="PING"),
        pytest.param("ARP", GATEWAY_DISABLED, id="ARP"),
        pytest.param("IPROUTE", GATEWAY_DISABLED, id="IPROUTE"),
        pytest.param("NRR N0PEER", b"Not found", id="NRR-no-route"),
    ],
)
def test_ip_gateway_command_without_gateway(linbpq, cmd, expected):
    with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
        client.login("test", "test")
        response = client.run_command(cmd)
    assert expected in response, (
        f"{cmd}: expected {expected!r}, got {response!r}"
    )
