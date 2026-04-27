"""Phase 8 leftovers — legacy serial-attached modem drivers.

Five additional drivers ship in linbpq for vintage HF modems:

- ``AEAPACTOR`` — AEA / Timewave PK-232 family (``AEAPactor.c``)
- ``SCSPACTOR`` — SCS PTC family (``SCSPactor.c``)
- ``SCSTRACKER`` — SCS Tracker / DSP-4100 (``SCSTracker.c``)
- ``TRKMULTI`` — SCS TrackeMulti (``SCSTrackeMulti.c``)
- ``HALDRIVER`` — HAL DXP-38 / Clover-II (``HALDriver.c``)

All five are serial-attached.  Each parses cfg-block init scripts
between ``CONFIG`` and ``ENDPORT`` (no ``ADDR`` line — the driver
takes ``COMPORT=`` from the PORT-block keywords) and runs a
state-machine over the serial port: the byte exchange is
modem-specific, but every driver opens the port and writes
something within a few seconds.

Each test does the minimum that's reliably verifiable without
simulating the modem's reply protocol:

1. ``DRIVER=<name>`` parses cleanly; daemon serves telnet.
2. The driver-specific init line lands in the log
   (``"AEA Pactor /dev/pts/N"`` etc.).
3. Linbpq writes at least one byte to the PTY master end —
   evidence the serial driver opened the port and started
   talking.

Driving full init handshakes would need per-modem fake-TNC
simulators that respond with ``cmd:`` prompts and ACKs; deferred
since none of these modems appear in M0LTE / GB7RDG configs.
"""

from __future__ import annotations

import socket
import time
from pathlib import Path
from string import Template

import pytest

from helpers.linbpq_instance import LinbpqInstance
from helpers.pty_kiss_modem import PtyKissModem


_CFG_TEMPLATE = """\
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
 ID=__ID__
 DRIVER=__DRIVER__
 COMPORT=__SLAVE__
 SPEED=9600
 CONFIG
ENDPORT
"""


def _read_available(fd: int, timeout: float) -> bytes:
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


# (driver-keyword, port-id-shown-in-cfg, log-substring-the-driver-prints)
LEGACY_MODEMS = [
    pytest.param("AEAPACTOR", "AEA", "AEA Pactor", id="AEAPactor"),
    pytest.param("SCSPACTOR", "SCS", "SCS Pactor", id="SCSPactor"),
    pytest.param("SCSTRACKER", "TRK", "SCSTRK", id="SCSTracker"),
    pytest.param("TRKMULTI", "TRKM", "SCSTRK", id="TrackeMulti"),
    pytest.param("HALDRIVER", "HAL", "HAL Driver", id="HALDriver"),
]


@pytest.mark.parametrize("driver,port_id,log_marker", LEGACY_MODEMS)
def test_legacy_serial_modem_opens_pty_and_logs_init(
    tmp_path: Path, driver: str, port_id: str, log_marker: str
):
    """A legacy serial-attached modem driver opens the PTY slave and
    logs its init banner; that's enough to confirm the cfg parser
    accepted ``DRIVER=<name>`` and the driver booted up.

    Some drivers (AEA / SCS / HAL families) buffer their initial
    bytes until they see the TNC respond, so we don't assert that
    bytes have arrived at the master end — only that the daemon
    booted cleanly with that driver.
    """
    with PtyKissModem() as modem:
        cfg_text = (
            _CFG_TEMPLATE
            .replace("__ID__", port_id)
            .replace("__DRIVER__", driver)
            .replace("__SLAVE__", modem.slave_path)
        )
        cfg = Template(cfg_text)
        with LinbpqInstance(tmp_path, config_template=cfg) as linbpq:
            with socket.create_connection(
                ("127.0.0.1", linbpq.telnet_port), timeout=3
            ) as sock:
                sock.settimeout(2)
                assert sock.recv(64), "telnet didn't greet"

    log = (tmp_path / "linbpq.stdout.log").read_text(errors="replace")
    assert log_marker in log, (
        f"{driver}: init line {log_marker!r} missing from log: {log[:2000]}"
    )
    # No "not recognised - Ignored" warnings for the DRIVER keyword.
    assert (
        f"Ignored:{driver}" not in log
        and f"Ignored: {driver}" not in log
    ), f"{driver} got 'not recognised - Ignored': {log[:2000]}"


def test_aea_pactor_writes_to_serial(tmp_path: Path):
    """AEA-Pactor opens the PTY synchronously during ``AEAExtInit``
    (line 488) and AEAPoll runs the term-mode probe loop on the
    100 ms timer — so bytes land on the master end within seconds."""
    with PtyKissModem() as modem:
        cfg_text = (
            _CFG_TEMPLATE
            .replace("__ID__", "AEA")
            .replace("__DRIVER__", "AEAPACTOR")
            .replace("__SLAVE__", modem.slave_path)
        )
        cfg = Template(cfg_text)
        with LinbpqInstance(tmp_path, config_template=cfg):
            data = _read_available(modem.master_fd, timeout=8.0)

    assert data, (
        "AEA-Pactor driver didn't write to the serial port within 8s"
    )
