"""WinRPR (SCS Tracker / Robust-Packet) modem driver coverage.

WinRPR is a TCP-attached modem.  Driver in ``WinRPR.c``: the cfg
block syntax matches VARA/ARDOP (``ADDR <ip> <port>``), but linbpq
opens only **one** TCP socket (no separate data port) — see
``WinRPRThread`` lines 1519/1541.

Coverage limited to dial-out: linbpq attempts a TCP connect to the
configured ``ADDR`` within a few seconds of startup.  The init
script is sent via the ExtProc poll mechanism (not the connect
thread itself), and we don't simulate the SCS Tracker reply
protocol — so we don't go further than connect-establishment.
"""

from __future__ import annotations

from pathlib import Path
from string import Template

from helpers.cmdport_app import cmdport_app
from helpers.linbpq_instance import LinbpqInstance


def _winrpr_cfg(port: int) -> Template:
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
 ID=WinRPR
 DRIVER=WINRPR
 CONFIG
 ADDR 127.0.0.1 {port}
ENDPORT
"""
    )


def test_winrpr_dials_out_to_configured_addr(tmp_path: Path):
    """``DRIVER=WINRPR`` + ``ADDR 127.0.0.1 <port>`` makes linbpq
    dial out to that TCP port within ~5s of startup."""
    with cmdport_app() as listener:
        cfg = _winrpr_cfg(listener.port)
        with LinbpqInstance(tmp_path, config_template=cfg):
            # WinRPRThread sleeps 3s then connects; allow 10s slack.
            assert listener.wait_for_client(timeout=15.0), (
                "linbpq did not dial out to the WinRPR TNC"
            )
