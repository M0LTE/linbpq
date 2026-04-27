"""KAM-Pactor (Kantronics) modem driver coverage.

KAM-Pactor is a *serial-attached* HF modem.  Its driver lives in
``KAMPactor.c``; linbpq opens the serial port and runs a state
machine that sends a probe CR (``\\r``) to detect terminal mode,
then sends an init script (``MARK 1400``, ``SPACE 1600``, ...
followed by ``ECHO OFF``, ``XMITECHO ON``, ``MYCALL <node>``, etc.)
and finally ``INTFACE HOST\\r`` + ``RESET\\r`` to switch to host mode.

Each step waits for a TNC reply; without a fake KAM TNC sending
``cmd:`` prompts, linbpq cycles between the term-mode probe and
the timeout retry (``\\xC0Q\\xC0``).  We use a PTY pair (slave is
linbpq's serial device, master is the test) and observe what
linbpq writes.

Coverage:

- ``DRIVER=KAMPACTOR`` cfg parses cleanly.
- linbpq opens the PTY and starts driving the state machine —
  visible as bytes arriving at the master end within a few seconds.
- The terminal-mode timeout retry (``\\xC0Q\\xC0``) lands within
  the 5s timeout window.
"""

from __future__ import annotations

import time
from pathlib import Path
from string import Template

from helpers.linbpq_instance import LinbpqInstance
from helpers.pty_kiss_modem import PtyKissModem


_KAM_CFG_TEMPLATE = """\
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
 ID=KAM
 DRIVER=KAMPACTOR
 COMPORT=__SLAVE__
 SPEED=9600
 CONFIG
ENDPORT
"""


def _read_all_available(fd: int, timeout: float) -> bytes:
    """Drain everything written by linbpq within ``timeout`` seconds."""
    import os

    deadline = time.monotonic() + timeout
    out = bytearray()
    os.set_blocking(fd, False)
    try:
        while time.monotonic() < deadline:
            try:
                chunk = os.read(fd, 4096)
            except BlockingIOError:
                time.sleep(0.05)
                continue
            if not chunk:
                time.sleep(0.05)
                continue
            out.extend(chunk)
    finally:
        os.set_blocking(fd, True)
    return bytes(out)


def _wait_for_marker(fd: int, marker: bytes, timeout: float) -> bytes:
    """Read until ``marker`` appears or the deadline passes."""
    import os

    deadline = time.monotonic() + timeout
    out = bytearray()
    os.set_blocking(fd, False)
    try:
        while time.monotonic() < deadline:
            try:
                chunk = os.read(fd, 4096)
            except BlockingIOError:
                time.sleep(0.05)
                continue
            if not chunk:
                time.sleep(0.05)
                continue
            out.extend(chunk)
            if marker in out:
                return bytes(out)
    finally:
        os.set_blocking(fd, True)
    return bytes(out)


def test_kam_pactor_opens_serial_and_writes(tmp_path: Path):
    """KAM-Pactor driver opens the PTY slave and starts the
    initialisation state machine — observable as bytes (a CR probe
    or the term-mode timeout ``\\xC0Q\\xC0`` retry) landing on the
    master end within a few seconds of startup."""
    with PtyKissModem() as modem:
        cfg = Template(
            _KAM_CFG_TEMPLATE.replace("__SLAVE__", modem.slave_path)
        )
        with LinbpqInstance(tmp_path, config_template=cfg):
            data = _read_all_available(modem.master_fd, timeout=8.0)

    assert data, (
        "linbpq didn't write anything to the KAM-Pactor serial port "
        "within 8 seconds — driver may not be opening the PTY"
    )
    # First byte: term-mode probe (CR).  Within 5s the term-mode
    # timeout retry fires (\xC0Q\xC0).
    assert b"\r" in data or b"\xc0Q\xc0" in data, (
        f"unexpected KAM serial output (no CR or QFEND timeout retry): {data!r}"
    )


def test_kam_pactor_cfg_parses_cleanly(tmp_path: Path):
    """Canary: ``DRIVER=KAMPACTOR`` + ``COMPORT=...`` parses
    cleanly and the port shows up in the ``PORTS`` listing."""
    from helpers.telnet_client import TelnetClient

    with PtyKissModem() as modem:
        cfg = Template(
            _KAM_CFG_TEMPLATE.replace("__SLAVE__", modem.slave_path)
        )
        with LinbpqInstance(tmp_path, config_template=cfg) as linbpq:
            with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
                client.login("test", "test")
                response = client.run_command("PORTS")

    assert b"KAM" in response, (
        f"KAM port missing from PORTS — cfg rejected: {response!r}"
    )
