"""ARDOP HF modem driver coverage.

ARDOP is a TCP-attached HF modem.  Driver lives in ``ARDOP.c``; the
on-the-wire shape of the linbpq → ARDOPC connection is the same as
VARA — two adjacent TCP sockets (control + ``port + 1`` data),
~3s start-up sleep, plain-ASCII commands terminated by ``\\r``.

Difference from VARA: post-INIT-script linbpq sends ``LISTEN TRUE``
(VARA sends ``LISTEN ON``), and the cfg block accepts ``ADDR``,
``TCPSERIAL``, ``SERIAL``, or ``I2C`` as the first keyword.

We reuse :class:`helpers.vara_modem.VaraModem` since both modems
present the same two-port TCP simulator interface.
"""

from __future__ import annotations

from pathlib import Path
from string import Template

from helpers.linbpq_instance import LinbpqInstance
from helpers.vara_modem import vara_modem as tcp_pair_modem


def _ardop_cfg(ctrl_port: int) -> Template:
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
 ID=ARDOP
 DRIVER=ARDOP
 CONFIG
 ADDR 127.0.0.1 {ctrl_port}
ENDPORT
"""
    )


def test_ardop_dials_out_to_control_and_data_sockets(tmp_path: Path):
    """``DRIVER=ARDOP`` + ``ADDR 127.0.0.1 <port>`` → linbpq dials
    both adjacent TCP ports the ARDOPC TNC listens on."""
    with tcp_pair_modem() as modem:
        cfg = _ardop_cfg(modem.control_port)
        with LinbpqInstance(tmp_path, config_template=cfg):
            assert modem.wait_for_both_connected(timeout=15.0), (
                "linbpq did not connect both ARDOP control + data sockets"
            )


def test_ardop_sends_mycall_and_listen_true(tmp_path: Path):
    """After both sockets connect, linbpq's INIT script lands
    ``MYCALL N0CALL`` plus the post-script ``LISTEN TRUE``
    on the control socket."""
    with tcp_pair_modem() as modem:
        cfg = _ardop_cfg(modem.control_port)
        with LinbpqInstance(tmp_path, config_template=cfg):
            assert modem.wait_for_both_connected(timeout=15.0)
            buf = modem.wait_for_control_data(b"LISTEN TRUE", timeout=15.0)

    assert b"MYCALL N0CALL" in buf, (
        f"ARDOP INIT missing MYCALL: {buf!r}"
    )
    assert b"LISTEN TRUE" in buf, (
        f"ARDOP INIT missing LISTEN TRUE: {buf!r}"
    )
