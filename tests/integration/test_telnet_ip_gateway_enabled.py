"""Phase 3 deferral — IP-gateway commands with the gateway enabled.

The default fixture has no IPGATEWAY block, so PING / ARP / IPROUTE
report "IP Gateway is not enabled" (covered in
test_telnet_ip_gateway.py).  Here we use the ``linbpq_ipgw`` fixture
(IP_GATEWAY_CONFIG with a minimal LAN adapter declared) to lock in
the *enabled* path: the commands return real status output.
"""

from __future__ import annotations

from helpers.telnet_client import TelnetClient


def test_iproute_lists_locked_default(linbpq_ipgw):
    """IPROUTE returns the locked default route added at gateway init."""
    with TelnetClient("127.0.0.1", linbpq_ipgw.telnet_port) as client:
        client.login("test", "test")
        response = client.run_command("IPROUTE")
    assert b"Entries" in response, f"no 'Entries' header: {response!r}"
    assert b"Locked" in response, (
        f"no Locked entry in routes: {response!r}"
    )


def test_arp_returns_table(linbpq_ipgw):
    """ARP returns successfully (empty table is fine — locked in as
    'no IP Gateway not enabled' message anywhere)."""
    with TelnetClient("127.0.0.1", linbpq_ipgw.telnet_port) as client:
        client.login("test", "test")
        response = client.run_command("ARP")
    assert b"IP Gateway is not enabled" not in response, (
        f"ARP still reports gateway disabled: {response!r}"
    )
    assert b"TEST:N0CALL}" in response


def test_nat_returns_table(linbpq_ipgw):
    with TelnetClient("127.0.0.1", linbpq_ipgw.telnet_port) as client:
        client.login("test", "test")
        response = client.run_command("NAT")
    assert b"IP Gateway is not enabled" not in response, (
        f"NAT still reports gateway disabled: {response!r}"
    )
    assert b"TEST:N0CALL}" in response


def test_ping_unreachable_host_returns_no_route(linbpq_ipgw):
    """PINGing an address that isn't on our (private, in-memory) LAN
    returns 'No Route to Host' rather than a real ping reply — and
    crucially does not return the gateway-disabled message."""
    with TelnetClient("127.0.0.1", linbpq_ipgw.telnet_port) as client:
        client.login("test", "test")
        response = client.run_command("PING 10.99.99.99")
    assert b"IP Gateway is not enabled" not in response, (
        f"PING still reports gateway disabled: {response!r}"
    )
    assert b"No Route to Host" in response, (
        f"unexpected PING response: {response!r}"
    )


def test_axmheard_without_port_is_rejected(linbpq_ipgw):
    """AXMHEARD needs a port number; absent one, returns 'Invalid Port'."""
    with TelnetClient("127.0.0.1", linbpq_ipgw.telnet_port) as client:
        client.login("test", "test")
        response = client.run_command("AXMHEARD")
    assert b"Invalid Port" in response, (
        f"AXMHEARD without port unexpected: {response!r}"
    )


def test_axresolver_without_port_is_rejected(linbpq_ipgw):
    with TelnetClient("127.0.0.1", linbpq_ipgw.telnet_port) as client:
        client.login("test", "test")
        response = client.run_command("AXRESOLVER")
    assert b"Invalid Port" in response, (
        f"AXRESOLVER without port unexpected: {response!r}"
    )
