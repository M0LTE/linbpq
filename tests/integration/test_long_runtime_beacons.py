"""Long-runtime beacon coverage — ID and BT timer-driven UI frames.

Covers two cfg-driven beacons that fire on minute-scale timers and
were previously deferred from the ``IDMSG:`` / ``BTEXT:`` cfg-block
acceptance tests in ``test_config_keyword_acceptance.py``.

Timer mechanics (verified against ``cMain.c`` / ``L3Code.c``):

- ``IDINTERVAL`` / ``BTINTERVAL`` are the cfg keywords; both in
  minutes.
- On boot, ``IDTIMER = BTTIMER = 2`` (cMain.c:823 / cMain.c:827) if
  the corresponding interval is non-zero.
- ``L3TimerProc()`` runs once per minute (cMain.c:2220), decrements
  each timer; when a timer hits 0 it fires ``SENDIDMSG`` /
  ``SENDBTMSG`` (L3Code.c:1075 / L3Code.c:1088) and reloads from
  ``IDINTERVAL`` / ``BTINTERVAL``.
- ``SENDIDMSG`` queues a UI frame addressed to ``ID`` on every port
  with ``PROTOCOL < 10``; frame body is the ``IDMSG:`` block text
  (cMain.c:1493).
- ``SENDBTMSG`` queues a UI frame addressed to that port's ``UNPROTO=``
  destination; body is the ``BTEXT:`` block text (cMain.c:802).
- ``L3FastTimer`` dequeues from ``IDMSG_Q`` once per 10 seconds
  (L3Code.c:1156) and ``PUT_ON_PORT_Q`` hands it to the port driver
  (L3Code.c:1167).

So the first ID/BT frame lands on the port roughly two minutes after
boot, plus the worst-case 10-second IDMSG_Q drain delay.

The single test below exercises both beacons in one boot to amortise
the wait — set ``IDINTERVAL=1 BTINTERVAL=1``, configure a KISS-on-PTY
port with ``UNPROTO=BEACON``, then read from the PTY master and look
for both frames.

Marked ``@pytest.mark.long_runtime`` so ``conftest.py``'s ordering
hook sorts it to the front of the xdist queue — workers pick it up
first and run it in parallel with the rest of the suite, minimising
the impact on overall runtime.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from string import Template

import pytest

from helpers.linbpq_instance import LinbpqInstance
from helpers.pty_kiss_modem import (
    PtyKissModem,
    ax25_decode_call,
    kiss_decode_frames,
)


_BEACON_CFG_TEMPLATE = """\
SIMPLE=1
NODECALL=N0CALL
NODEALIAS=BCN
LOCATOR=NONE
IDINTERVAL=1
BTINTERVAL=1

IDMSG:
N0CALL ID Beacon Test 0xCAFE
***

BTEXT:
N0CALL BT Beacon Test 0xBABE
***

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
 ID=KissBeacon
 TYPE=ASYNC
 PROTOCOL=KISS
 COMPORT=__SLAVE__
 SPEED=9600
 UNPROTO=BEACON
ENDPORT
"""


def _read_until_both(fd: int, marker_a: bytes, marker_b: bytes,
                     timeout: float) -> bytes:
    """Read from ``fd`` until both ``marker_a`` and ``marker_b`` have
    appeared in the running buffer, or the deadline passes."""
    deadline = time.monotonic() + timeout
    out = bytearray()
    os.set_blocking(fd, False)
    try:
        while time.monotonic() < deadline:
            try:
                chunk = os.read(fd, 4096)
            except BlockingIOError:
                time.sleep(0.5)
                continue
            if not chunk:
                time.sleep(0.5)
                continue
            out.extend(chunk)
            if marker_a in out and marker_b in out:
                return bytes(out)
    finally:
        os.set_blocking(fd, True)
    return bytes(out)


@pytest.mark.long_runtime
def test_id_and_bt_beacons_fire_within_three_minutes(tmp_path: Path):
    """With ``IDINTERVAL=1`` and ``BTINTERVAL=1`` the first ID and BT
    UI frames land on the KISS port roughly two minutes after boot
    (initial timer = 2, decrements once per minute).  Allow up to
    180s for slow CI before declaring a failure.

    The ID frame's AX.25 destination is ``ID`` (cMain.c:1480 sets
    ``IDHDDR.DEST`` to AX.25-encoded ``"ID"``).  The BT frame's
    destination is the per-port ``UNPROTO=`` value (here
    ``BEACON``).  Bodies contain the cfg ``IDMSG:`` / ``BTEXT:``
    block text verbatim.
    """
    with PtyKissModem() as modem:
        cfg = Template(
            _BEACON_CFG_TEMPLATE.replace("__SLAVE__", modem.slave_path)
        )
        with LinbpqInstance(tmp_path, config_template=cfg):
            data = _read_until_both(
                modem.master_fd,
                b"Beacon Test 0xCAFE",
                b"Beacon Test 0xBABE",
                timeout=180.0,
            )

    assert b"Beacon Test 0xCAFE" in data, (
        "ID beacon body not seen on KISS port within 180s — "
        f"got {len(data)} bytes"
    )
    assert b"Beacon Test 0xBABE" in data, (
        "BT beacon body not seen on KISS port within 180s — "
        f"got {len(data)} bytes"
    )

    # Decode the KISS frames and check the AX.25 destinations.  The
    # ID destination is "ID" (padded with shifted spaces); the BT
    # destination is "BEACON" (from UNPROTO=).
    frames = kiss_decode_frames(data)
    dests = {ax25_decode_call(f[:7]) for f in frames if len(f) >= 7}
    assert "ID" in dests, (
        f"No UI frame addressed to 'ID' among decoded destinations: {dests}"
    )
    assert "BEACON" in dests, (
        f"No UI frame addressed to 'BEACON' among decoded destinations: {dests}"
    )
