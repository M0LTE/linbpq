"""HSMODEM (UDP-based) modem driver coverage.

HSMODEM is the modem from DG9VH/DJ0AB's "high speed modem" project.
linbpq's driver lives in ``HSMODEM.c`` and uses **UDP** (not TCP):

- linbpq *sends* poll datagrams to ``ADDR``'s port (the modem's
  command port — first byte ``0x3c``).
- linbpq *binds* a receive socket on ``port + 2``.

Polls fire every ~2s from the ExtProc 100ms timer (``PollDelay > 20``
in ``HSMODEM.c`` line 400).  We stand up a UDP listener as the
modem's command port and lock in that linbpq actually sends polls.
"""

from __future__ import annotations

from pathlib import Path
from string import Template

from helpers.linbpq_instance import LinbpqInstance
from helpers.udp_listener import udp_listener


def _hsmodem_cfg(cmd_port: int) -> Template:
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
 ID=HSModem
 DRIVER=HSMODEM
 CONFIG
 ADDR 127.0.0.1 {cmd_port}
 CAPTURE FakeCapture
 PLAYBACK FakePlayback
 MODE 9
ENDPORT
"""
    )
# CAPTURE / PLAYBACK are mandatory or HSMODEM segfaults — see issue
# filed in M0LTE/linbpq.  ``SendPoll`` ``strcpy``s these unconditionally
# from the cfg without a NULL guard.


def test_hsmodem_sends_udp_poll_to_command_port(tmp_path: Path):
    """linbpq sends UDP poll datagrams to the HSMODEM command port
    (``ADDR``'s port).  First byte should be ``0x3c`` (the poll
    msg-type) and the payload carries our NodeCall."""
    with udp_listener() as listener:
        cfg = _hsmodem_cfg(listener.port)
        with LinbpqInstance(tmp_path, config_template=cfg):
            datagram = listener.wait_for_datagram(timeout=10.0)

    assert datagram is not None, (
        "linbpq did not send a UDP poll to the HSMODEM command port"
    )
    # First byte is 0x3c (BroadcastMsg type) per HSMODEM.c line 1712.
    assert datagram[0] == 0x3C, (
        f"HSMODEM poll first byte expected 0x3c, got 0x{datagram[0]:02x}"
    )
    # PollMsg.Callsign[] carries our NodeCall.
    assert b"N0CALL" in datagram, (
        f"HSMODEM poll missing NodeCall: {datagram!r}"
    )
