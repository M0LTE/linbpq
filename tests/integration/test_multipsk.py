"""MULTIPSK driver coverage.

MULTIPSK is a TCP-attached HF/digital-modes app.  Driver in
``MULTIPSK.c`` parses ``ADDR <ip> <port>`` and dials out to that
single TCP port (no separate data socket).  ``Sleep(5000)`` happens
before connect, so the test budget is generous.

Single dial-out canary — locking in ``DRIVER=MULTIPSK`` cfg
acceptance and that linbpq actually connects.  The MPSK reply
protocol (``DIGITAL MODE ?`` query and friends) isn't simulated.
"""

from __future__ import annotations

from pathlib import Path
from string import Template

from helpers.cmdport_app import cmdport_app
from helpers.linbpq_instance import LinbpqInstance


def _multipsk_cfg(port: int) -> Template:
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
 ID=MPSK
 DRIVER=MULTIPSK
 CONFIG
 ADDR 127.0.0.1 {port}
ENDPORT
"""
    )


def test_multipsk_dials_out_to_configured_addr(tmp_path: Path):
    """``DRIVER=MULTIPSK`` + ``ADDR 127.0.0.1 <port>`` makes linbpq
    dial out to that TCP port.  Sleep(5000) before connect — allow
    plenty of slack."""
    with cmdport_app() as listener:
        cfg = _multipsk_cfg(listener.port)
        with LinbpqInstance(tmp_path, config_template=cfg):
            assert listener.wait_for_client(timeout=15.0), (
                "linbpq did not dial out to the MULTIPSK TNC"
            )
