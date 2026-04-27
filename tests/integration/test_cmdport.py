"""``CMDPORT`` — the LinBPQ Applications Interface.

linbpq's ``CMDPORT n m ...`` config keyword (inside the Telnet
driver's ``CONFIG`` block) declares an array of TCP ports —
``CMDPort[0]`` through ``CMDPort[32]``.  When a sysop session runs
``C <bpqport> HOST <slot> [K|S|NOCALL|TRANS]`` from the node
prompt, linbpq dials out to ``127.0.0.1:CMDPort[slot]`` and
bidirectionally relays the session.  This is how external apps
like TelStar, WALL and DAPPS are wired into the GB7RDG cfg.

Reference: [LinBPQ Applications Interface][appsiface].

[appsiface]: https://www.cantab.net/users/john.wiseman/Documents/LinBPQ%20Applications%20Interface.html
"""

from __future__ import annotations

from pathlib import Path
from string import Template

import time

from helpers.cmdport_app import cmdport_app
from helpers.linbpq_instance import LinbpqInstance
from helpers.telnet_client import TelnetClient


def _cfg_with_cmdport(app_port: int) -> Template:
    """A default-shaped cfg with a single CMDPORT entry pointing at
    the given TCP port (the fake app listener)."""
    return Template(
        f"""\
SIMPLE=1
NODECALL=N0CALL
NODEALIAS=TEST
LOCATOR=NONE

PORT
 ID=Telnet
 DRIVER=Telnet
 CONFIG
 TCPPORT=$telnet_port
 HTTPPORT=$http_port
 MAXSESSIONS=10
 USER=test,test,N0CALL,,SYSOP
 CMDPORT {app_port}
ENDPORT
"""
    )


def test_c_host_dials_out_to_cmdport_slot(tmp_path: Path):
    """``C 1 HOST 0`` opens a TCP connection from linbpq to the
    address declared at ``CMDPort[0]``.  The fake app's listener
    accepts within a few seconds, and linbpq emits the
    ``*** Connected to APPL`` confirmation back to the telnet
    user."""
    with cmdport_app() as app:
        cfg = _cfg_with_cmdport(app.port)
        with LinbpqInstance(tmp_path, config_template=cfg) as linbpq:
            with TelnetClient(
                "127.0.0.1", linbpq.telnet_port, timeout=10
            ) as client:
                client.login("test", "test")
                client.write_line("C 1 HOST 0")
                # Read what the user sees back.
                user_response = client.read_idle(idle_timeout=1.5, max_total=4.0)
                assert app.wait_for_client(timeout=4.0), (
                    "linbpq did not connect to CMDPort[0]"
                )

    assert b"Connected to APPL" in user_response, (
        f"no APPL connect confirmation: {user_response!r}"
    )


def test_cmdport_relays_app_to_user(tmp_path: Path):
    """Whatever the app sends back over its TCP connection appears
    in the user's telnet session."""
    with cmdport_app() as app:
        cfg = _cfg_with_cmdport(app.port)
        with LinbpqInstance(tmp_path, config_template=cfg) as linbpq:
            with TelnetClient(
                "127.0.0.1", linbpq.telnet_port, timeout=10
            ) as client:
                client.login("test", "test")
                client.write_line("C 1 HOST 0")
                client.read_idle(idle_timeout=1.0, max_total=3.0)
                assert app.wait_for_client(timeout=4.0)

                # App sends a banner; user should receive it.
                app.send(b"HELLO FROM FAKE APP\r\n")
                time.sleep(0.5)
                user_data = client.read_idle(idle_timeout=1.0, max_total=3.0)

    assert b"HELLO FROM FAKE APP" in user_data, (
        f"app->user relay missing payload: {user_data!r}"
    )


def test_cmdport_relays_user_to_app(tmp_path: Path):
    """Whatever the user types in the telnet session is delivered
    to the connected fake app."""
    with cmdport_app() as app:
        cfg = _cfg_with_cmdport(app.port)
        with LinbpqInstance(tmp_path, config_template=cfg) as linbpq:
            with TelnetClient(
                "127.0.0.1", linbpq.telnet_port, timeout=10
            ) as client:
                client.login("test", "test")
                client.write_line("C 1 HOST 0")
                client.read_idle(idle_timeout=1.0, max_total=3.0)
                assert app.wait_for_client(timeout=4.0)

                # linbpq sends the user's callsign as a signon line
                # automatically; drain that first.
                app.recv_until(b"\r", timeout=2.0)

                # Now type something — should arrive at the app.
                client.write_line("from-the-user")
                time.sleep(0.5)
                app_data = app.recv_until(b"from-the-user", timeout=2.0)

    assert b"from-the-user" in app_data, (
        f"user->app relay missing payload: {app_data!r}"
    )


def test_cmdport_invalid_slot_returns_error(tmp_path: Path):
    """``C 1 HOST 7`` when only slot 0 is configured returns
    ``Error - Invalid HOST Port``."""
    with cmdport_app() as app:
        cfg = _cfg_with_cmdport(app.port)
        with LinbpqInstance(tmp_path, config_template=cfg) as linbpq:
            with TelnetClient(
                "127.0.0.1", linbpq.telnet_port, timeout=10
            ) as client:
                client.login("test", "test")
                client.write_line("C 1 HOST 7")
                response = client.read_idle(idle_timeout=1.5, max_total=4.0)

    assert b"Invalid HOST Port" in response, (
        f"unexpected response for invalid slot: {response!r}"
    )
