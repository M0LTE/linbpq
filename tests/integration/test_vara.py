"""VARA HF modem driver coverage.

VARA is a TCP-attached HF modem.  Its driver lives in ``VARA.c``;
linbpq's role is the *client* — it dials out to the VARA TNC's two
adjacent TCP ports (``port`` for control, ``port + 1`` for data),
sleeps a beat, then sends an init script (``MYCALL ...\\r`` then any
mode keywords from the cfg block, then ``LISTEN ON\\r``).

The fake TNC simulator (``helpers/vara_modem.py``) accepts both
sockets and records bytes for test inspection.  We don't model
VARA's RDY/CONNECTED reply protocol — just lock in the dial-out and
the leading INIT-script frames.
"""

from __future__ import annotations

from pathlib import Path
from string import Template

from helpers.linbpq_instance import LinbpqInstance
from helpers.vara_modem import vara_modem


def _vara_cfg(ctrl_port: int) -> Template:
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
ENDPORT

PORT
 PORTNUM=2
 ID=VARA
 DRIVER=VARA
 CONFIG
 ADDR 127.0.0.1 {ctrl_port}
ENDPORT
"""
    )


def test_vara_dials_out_to_control_and_data_sockets(tmp_path: Path):
    """``DRIVER=VARA`` + ``ADDR 127.0.0.1 <port>`` makes linbpq dial
    *both* adjacent TCP ports the VARA TNC listens on."""
    with vara_modem() as modem:
        cfg = _vara_cfg(modem.control_port)
        with LinbpqInstance(tmp_path, config_template=cfg):
            # VARAThread sleeps 3s before the connect attempt; allow
            # 10s slack for the connect + accept on both sockets.
            assert modem.wait_for_both_connected(timeout=15.0), (
                "linbpq did not connect both VARA control + data sockets"
            )


def test_vara_sends_mycall_and_listen_on(tmp_path: Path):
    """After both sockets connect, linbpq sends the INIT script on
    the control socket: ``MYCALL <NodeCall>\\r`` followed by
    ``LISTEN ON\\r`` (plus any cfg-block init lines we'd added)."""
    with vara_modem() as modem:
        cfg = _vara_cfg(modem.control_port)
        with LinbpqInstance(tmp_path, config_template=cfg):
            assert modem.wait_for_both_connected(timeout=15.0), (
                "VARA sockets never connected"
            )
            # INIT script is sent ~1s after the second connect; give
            # generous slack for slower CI hosts.
            buf = modem.wait_for_control_data(b"LISTEN ON", timeout=15.0)

    assert b"MYCALL N0CALL" in buf, (
        f"VARA INIT script missing MYCALL: {buf!r}"
    )
    assert b"LISTEN ON" in buf, (
        f"VARA INIT script missing LISTEN ON: {buf!r}"
    )


def test_vara_cfg_init_keywords_forwarded(tmp_path: Path):
    """Cfg-block keywords like ``BW2300`` end up in the INIT script
    that linbpq sends to the TNC over the control socket."""
    cfg_template = Template(
        """\
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
ENDPORT

PORT
 PORTNUM=2
 ID=VARA
 DRIVER=VARA
 CONFIG
 ADDR 127.0.0.1 $ctrl_port
 BW2300
ENDPORT
"""
    )

    with vara_modem() as modem:
        # Tack ctrl_port onto the substitutions Template.substitute
        # expects via a custom render — easier to inline via .safe_substitute.
        rendered = cfg_template.safe_substitute(ctrl_port=modem.control_port)
        cfg = Template(rendered)
        with LinbpqInstance(tmp_path, config_template=cfg):
            assert modem.wait_for_both_connected(timeout=15.0)
            buf = modem.wait_for_control_data(b"BW2300", timeout=15.0)

    assert b"BW2300" in buf, (
        f"cfg-block BW2300 didn't reach VARA TNC: {buf!r}"
    )
