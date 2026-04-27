"""FLDigi/FLARQ modem driver coverage.

linbpq's FLDigi driver (``FLDigi.c``) talks to the FLDigi modem
over **two** TCP sockets:

- The **XML-RPC control** port (``port + 40``; default 7362)
- The **ARQ data** port (``port``; default 7322)

``ADDR <ip> <port>`` configures the ARQ port, and linbpq derives
the XML-RPC port from it.  Once connected, linbpq polls FLDigi via
XML-RPC ~every second — visible as ``POST /RPC2 HTTP/1.1`` on the
control socket.  That's our reliable signature for "linbpq is
talking to FLDigi".
"""

from __future__ import annotations

from pathlib import Path
from string import Template

from helpers.fldigi_modem import fldigi_modem
from helpers.linbpq_instance import LinbpqInstance


def _fldigi_cfg(arq_port: int) -> Template:
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
 ID=FLDIGI
 DRIVER=FLDIGI
 CONFIG
 ADDR 127.0.0.1 {arq_port}
 ARQMODE
ENDPORT
"""
    )


def test_fldigi_dials_out_to_xml_and_arq_sockets(tmp_path: Path):
    """``DRIVER=FLDIGI`` + ``ADDR 127.0.0.1 <port>`` makes linbpq dial
    both the ARQ port (configured) and the XML-RPC control port
    (``port + 40``)."""
    with fldigi_modem() as modem:
        cfg = _fldigi_cfg(modem.arq_port)
        with LinbpqInstance(tmp_path, config_template=cfg):
            # ConnecttoFLDigiThread sleeps 5s before connecting; allow
            # 15s slack on slower hosts.
            assert modem.wait_for_both_connected(timeout=20.0), (
                "linbpq did not connect both FLDigi XML-RPC + ARQ sockets"
            )


def test_fldigi_sends_xml_rpc_poll(tmp_path: Path):
    """Once connected, linbpq polls FLDigi via XML-RPC over the
    control socket — visible as ``POST /RPC2 HTTP/1.1``."""
    with fldigi_modem() as modem:
        cfg = _fldigi_cfg(modem.arq_port)
        with LinbpqInstance(tmp_path, config_template=cfg):
            assert modem.wait_for_both_connected(timeout=20.0)
            # XML-RPC poll fires once per second; the first useful
            # poll (main.get_trx_state) lands ~5 polls in.
            buf = modem.wait_for_xml_data(b"POST /RPC2 HTTP/1.1", timeout=15.0)

    assert b"POST /RPC2 HTTP/1.1" in buf, (
        f"FLDigi XML-RPC poll never landed: {buf!r}"
    )
    assert b"<methodCall>" in buf, (
        f"FLDigi XML-RPC body malformed: {buf!r}"
    )
