"""Fork addition: partner BBS link requests refused with DM.

When the BBS would turn a partner away anyway (an interlocked port or
group is busy, or the partner is locked out after MaxSessionTime), the
node now answers the partner's SABM with DM.  Before, it sent UA, the
BBS then rejected the session, and the node sent DISC (often more than
once), which costs airtime on a shared HF channel and looks to other
stations like the BBS calling someone mid-transfer.

Ordinary users still get UA, so the BBS can tell them why it's busy.

A PTY stands in for a KISS modem on port 2, so the tests send real
AX.25 frames and read the node's replies.  ``RefuseBBSLinkRequest``
in BBSSessionControl.c, hooked from ``L2SABM`` in L2Code.c.
"""

from __future__ import annotations

import time
from pathlib import Path
from string import Template

import pytest

from helpers.bpqmail_cfg import FwdPartner, render_bpqmail_cfg
from helpers.linbpq_instance import LinbpqInstance
from helpers.pty_kiss_modem import PtyKissModem, ax25_decode_call, kiss_decode_frames, kiss_encode


_NODE_CFG = """\
SIMPLE=1
NODECALL=N0AAA
NODEALIAS=AAA
LOCATOR=NONE

PORT
 ID=Telnet
 DRIVER=Telnet
 CONFIG
 TCPPORT=$telnet_port
 HTTPPORT=$http_port
 MAXSESSIONS=10
 USER=test,test,N0SDR,,SYSOP
ENDPORT

PORT
 PORTNUM=2
 ID=KissSerial
 TYPE=ASYNC
 PROTOCOL=KISS
 COMPORT=__SLAVE__
 SPEED=9600
 INTERLOCK=1
ENDPORT

APPLICATION 1,BBS,,N0AAA-1,BBS,255
"""

SABM = 0x2F
UA = 0x63
DM = 0x0F
PF = 0x10


def _call(call: str, command: bool, last: bool) -> bytes:
    base, _, ssid = call.partition("-")
    out = bytearray(b << 1 for b in base.ljust(6).upper().encode("ascii")[:6])
    out.append((0x80 if command else 0) | 0x60 | ((int(ssid or 0) & 0x0F) << 1) | (1 if last else 0))
    return bytes(out)


def _sabm(src: str, dest: str = "N0AAA-1") -> bytes:
    return kiss_encode(_call(dest, True, False) + _call(src, False, True) + bytes([SABM | PF]))


def _replies_to(modem: PtyKissModem, call: str, timeout: float) -> list[int]:
    """Control bytes (P/F bit removed) of frames sent to ``call``."""
    deadline = time.monotonic() + timeout
    buf = b""
    while time.monotonic() < deadline:
        buf += modem.read_available()
        time.sleep(0.1)
    ctls = []
    for frame in kiss_decode_frames(buf):
        if len(frame) >= 15 and ax25_decode_call(frame[0:7]) == call:
            ctls.append(frame[14] & ~PF)
    return ctls


def _wait_for_log(work_dir: Path, text: str, timeout: float) -> bool:
    # Refusals are logged from BBSSlowTimer, and the log is buffered
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if text in _bbs_log(work_dir):
            return True
        time.sleep(2)
    return False


def _partner(call: str, **overrides) -> FwdPartner:
    # Disabled, so linbpq never dials out
    overrides.setdefault("enabled", False)
    overrides.setdefault("con_timeout", 600)
    return FwdPartner(call=call, **overrides)


def _setup(work_dir: Path, modem: PtyKissModem, partners: list[FwdPartner]) -> LinbpqInstance:
    (work_dir / "linmail.cfg").write_text(
        render_bpqmail_cfg(bbs_call="N0AAA", sysop_call="N0AAA", hroute="GBR.EU", partners=partners)
    )
    cfg = Template(_NODE_CFG.replace("__SLAVE__", modem.slave_path))
    return LinbpqInstance(work_dir, config_template=cfg, extra_args=("mail",))


def _bbs_log(work_dir: Path) -> str:
    return "".join(p.read_text(errors="replace") for p in sorted((work_dir / "logs").glob("log_*_BBS.txt")))


def _start_mail_run(modem: PtyKissModem, call: str) -> None:
    """Connect a partner on port 2 and wait for the BBS to answer."""
    modem.read_available()
    modem.write(_sabm(call))
    ctls = _replies_to(modem, call, 3.0)
    assert UA in ctls, f"{call} should get UA on a free port, got {ctls!r}"


PARTNERS = [
    _partner("N0BBB", connect_script=["INTERLOCK 2", "C 2 N0BBB"]),
    _partner("N0CCC"),
]


@pytest.mark.parametrize(
    "interlock, reason",
    [("INTERLOCK 2", "Interlocked Port 2 is busy"), ("INTERLOCK GROUP 1", "Interlock Group 1 is busy")],
)
def test_partner_gets_dm_while_interlock_busy(tmp_path: Path, interlock: str, reason: str):
    """A second partner's SABM gets DM, not UA then DISC, while a
    partner session is on the interlocked port or group."""
    partners = [_partner("N0BBB", connect_script=[interlock, "C 2 N0BBB"]), _partner("N0CCC")]
    with PtyKissModem() as modem:
        with _setup(tmp_path, modem, partners):
            time.sleep(1)
            _start_mail_run(modem, "N0BBB")

            modem.write(_sabm("N0CCC-2"))
            ctls = _replies_to(modem, "N0CCC-2", 3.0)

            assert ctls == [DM], f"expected only DM to N0CCC-2, got {ctls!r}"
            text = f"Link request from N0CCC-2 on Port 2 refused with DM - {reason}"
            assert _wait_for_log(tmp_path, text, 60), f"no {text!r} in log: {_bbs_log(tmp_path)!r}"


def test_partner_gets_ua_when_port_free(tmp_path: Path):
    """Control: with nothing on the port, a partner's SABM gets UA."""
    with PtyKissModem() as modem:
        with _setup(tmp_path, modem, PARTNERS):
            time.sleep(1)
            _start_mail_run(modem, "N0CCC-2")


def test_partner_gets_ua_without_interlock(tmp_path: Path):
    """Control: with no script naming the port, two partners can
    connect at once."""
    with PtyKissModem() as modem:
        with _setup(tmp_path, modem, [_partner("N0BBB"), _partner("N0CCC")]):
            time.sleep(1)
            _start_mail_run(modem, "N0BBB")
            _start_mail_run(modem, "N0CCC")


def test_user_still_gets_ua_while_port_busy(tmp_path: Path):
    """An ordinary user isn't refused at link level, so the BBS can
    tell them mail forwarding is in progress."""
    with PtyKissModem() as modem:
        with _setup(tmp_path, modem, PARTNERS):
            time.sleep(1)
            _start_mail_run(modem, "N0BBB")

            modem.write(_sabm("N0DDD"))
            ctls = _replies_to(modem, "N0DDD", 3.0)

    assert ctls and ctls[0] == UA, f"user should get UA first, got {ctls!r}"
