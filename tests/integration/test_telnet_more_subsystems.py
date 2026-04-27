"""Phase 3 deferral — subsystem commands without their subsystems.

Each of these reports a recognisable "not configured" or
"not applicable" error in our config, where the relevant subsystem
is absent. Lock that in.
"""

from __future__ import annotations

from helpers.telnet_client import TelnetClient


def test_aprs_help_lists_subcommands(linbpq):
    """``APRS ?`` prints the subcommand list — works without any APRS port."""
    with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
        client.login("test", "test")
        response = client.run_command("APRS ?")
    assert b"APRS Subcommmands" in response, (
        f"APRS ? did not show subcommand list: {response!r}"
    )
    assert b"STATUS" in response
    assert b"BEACON" in response


def test_wl2ksysop_without_winlink_reports_unconfigured(linbpq):
    with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
        client.login("test", "test")
        client.run_command("PASSWORD")
        response = client.run_command("WL2KSYSOP")
    assert b"Winlink reporting is not configured" in response, (
        f"unexpected WL2KSYSOP response: {response!r}"
    )


def test_radio_without_rig_control_reports_unconfigured(linbpq):
    with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
        client.login("test", "test")
        response = client.run_command("RADIO")
    assert b"Rig Control not configured" in response, (
        f"unexpected RADIO response: {response!r}"
    )


def test_pollnodes_without_port_is_rejected(linbpq):
    """``POLLNODES`` with no port number returns "Invalid Port"
    (Cmd.c:319) — recognised command, just missing arg."""
    with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
        client.login("test", "test")
        client.run_command("PASSWORD")
        response = client.run_command("POLLNODES")
    assert b"Invalid Port" in response, (
        f"POLLNODES without port unexpected: {response!r}"
    )


def test_pollnodes_on_zero_quality_port_rejected(linbpq):
    """``POLLNODES`` on a port with ``PORTQUALITY == 0`` (the Telnet
    port in our default config) returns ``Quality = 0 or INP3 Port``
    rather than emitting a poll (Cmd.c:324)."""
    with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
        client.login("test", "test")
        client.run_command("PASSWORD")
        response = client.run_command("POLLNODES 1")
    assert b"Quality = 0" in response or b"INP3 Port" in response, (
        f"POLLNODES on Telnet port unexpected: {response!r}"
    )


def test_sendrif_without_neighbour_is_rejected(linbpq):
    """``SENDRIF <port> <call>`` requires a configured NET/ROM
    neighbour route on that port; without one the response is
    "Route not found" (Cmd.c:390)."""
    with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
        client.login("test", "test")
        client.run_command("PASSWORD")
        response = client.run_command("SENDRIF 2 N0PEER")
    assert b"Route not found" in response, (
        f"SENDRIF without route unexpected: {response!r}"
    )


def test_rhp_dumps_session_table(linbpq):
    """``RHP`` (sysop) dumps the Remote Host Protocol session table
    (``RHP.c:807``).  Paula G8PZT's RHP — used by WhatsPac and other
    remote-host clients (see header comment in RHP.c).  With no RHP
    sessions active the table has no rows, but the header line is
    always emitted — our reliable canary for the command being
    recognised.

    See also OARC packet white-papers
    (https://wiki.oarc.uk/packet:white-papers) for the protocol
    documentation.
    """
    with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
        client.login("test", "test")
        client.run_command("PASSWORD")
        response = client.run_command("RHP")
    assert b"Stream" in response and b"Local" in response and b"Remote" in response, (
        f"RHP didn't return the session-table header: {response!r}"
    )


def test_stopport_on_non_kiss_port_is_rejected(linbpq):
    """STOPPORT and STARTPORT only operate on KISS ports.  Our AXIP
    port (slot 2) isn't KISS; both commands should reject cleanly."""
    with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
        client.login("test", "test")
        client.run_command("PASSWORD")
        stop_resp = client.run_command("STOPPORT 2")
        start_resp = client.run_command("STARTPORT 2")
    assert b"Not a KISS Port" in stop_resp, f"STOPPORT 2: {stop_resp!r}"
    assert b"Not a KISS Port" in start_resp, f"STARTPORT 2: {start_resp!r}"
