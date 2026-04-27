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
