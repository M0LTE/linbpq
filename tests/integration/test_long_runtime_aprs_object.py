"""Long-runtime APRS object beacon coverage.

The ``OBJECT`` keyword inside an ``APRSDIGI`` ... ``****`` block
declares a periodic UI beacon:

    OBJECT PATH=<dest[,via...]> PORT=<port[,IS]> INTERVAL=<min> TEXT=<body>

Timer mechanics (verified against ``APRSCode.c``):

- ``ObjectList`` is built during ``APRSReadConfigFile`` (line 1799+).
- Each object's ``Timer`` is initialised to ``ObjectCount * 10 + 30``
  seconds (line 1811) so they spread out — first object fires at
  ~30 s, second at ~40 s, etc.
- ``DoSecTimer`` runs once per second from ``Poll_APRS`` (line 977)
  and decrements each object's ``Timer``; when it hits 0
  ``SendObject`` fires (line 2812) and the timer reloads to
  ``Interval * 60``.
- ``SendObject`` (line 2701) builds a UI frame addressed to the
  object's PATH dest, body = TEXT, and ships it via
  ``Send_AX_Datagram`` to every port in the PORT= list.

So a single OBJECT with ``PORT=2`` lands its first beacon on a
KISS-on-PTY port within ~30 seconds of boot.

PATH-specific behaviour: a literal first token of ``APRS`` resolves
to the runtime ``APRSDest`` (default ``APBPQ1``, APRSCode.c:1820);
``APRS-0`` maps to literal ``APRS``; anything else is taken
verbatim.  We use ``PATH=APRS`` and assert against ``APBPQ1``.

Marked ``@pytest.mark.long_runtime`` for consistency with the ID/BT
tests in ``test_long_runtime_beacons.py``; ``conftest.py``'s
``pytest_collection_modifyitems`` sorts the marker to the front of
the xdist queue so it runs in parallel with the rest of the suite.
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


_APRS_OBJECT_CFG_TEMPLATE = """\
SIMPLE=1
NODECALL=N0CALL
NODEALIAS=BCN
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
 ID=KissAprs
 TYPE=ASYNC
 PROTOCOL=KISS
 COMPORT=__SLAVE__
 SPEED=9600
ENDPORT

APRSDIGI
LAT=5126.83N
LON=00101.62W
StatusMsg=APRS Object Test
Symbol=B
Symset=/
OBJECT PATH=APRS PORT=2 INTERVAL=10 TEXT=APRS Object Test 0xFEED
****
"""


def _read_until(fd: int, marker: bytes, timeout: float) -> bytes:
    """Read from ``fd`` until ``marker`` appears in the running
    buffer or the deadline passes."""
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
            if marker in out:
                return bytes(out)
    finally:
        os.set_blocking(fd, True)
    return bytes(out)


@pytest.mark.long_runtime
def test_aprs_object_beacon_fires_within_ninety_seconds(tmp_path: Path):
    """A single APRSDIGI ``OBJECT`` with ``PORT=2`` fires its first
    UI beacon on the KISS-on-PTY port within ~30 seconds (initial
    Timer = 30 s, see APRSCode.c:1811).  Allow up to 90 s for slow
    CI before declaring a failure.

    Frame format: AX.25 UI frame addressed to the runtime
    ``APRSDest`` (default ``APBPQ1``).  Body is the cfg ``TEXT=``
    string verbatim (truncated to 80 chars at parse time, line 1851).
    """
    with PtyKissModem() as modem:
        cfg = Template(
            _APRS_OBJECT_CFG_TEMPLATE.replace("__SLAVE__", modem.slave_path)
        )
        with LinbpqInstance(tmp_path, config_template=cfg):
            data = _read_until(
                modem.master_fd,
                b"APRS Object Test 0xFEED",
                timeout=90.0,
            )

    assert b"APRS Object Test 0xFEED" in data, (
        "APRS object beacon body not seen on KISS port within 90 s — "
        f"got {len(data)} bytes"
    )

    frames = kiss_decode_frames(data)
    dests = {ax25_decode_call(f[:7]) for f in frames if len(f) >= 7}
    assert "APBPQ1" in dests, (
        f"No UI frame addressed to APRSDest 'APBPQ1' among decoded "
        f"destinations: {dests}"
    )
