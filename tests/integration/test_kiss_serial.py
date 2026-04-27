"""Phase 8 starter — KISS-on-serial via PTY.

Locks in the serial-port code path that's untouched by the existing
KISS-TCP coverage.  We use ``os.openpty()`` to hand linbpq a real
serial-looking device; linbpq opens the slave node and the test
drives the master end.

Two invariants:

1. Linbpq actually opens the PTY (boot log says
   ``Initialising Port 02   ASYNC /dev/pts/N Chan A``).
2. End-to-end frame ingest: a KISS-framed AX.25 UI frame written
   to the master end of the PTY shows up in linbpq's MH list with
   the source callsign.
"""

from __future__ import annotations

import socket
import time
from pathlib import Path
from string import Template

from helpers.linbpq_instance import LinbpqInstance
from helpers.pty_kiss_modem import (
    PtyKissModem,
    ax25_decode_call,
    kiss_decode_frames,
    kiss_encode,
)
from helpers.telnet_client import TelnetClient


# COMPORT gets substituted at runtime to the PTY slave path.
# AGWPORT included so the cross-protocol monitor test can connect.
KISS_SERIAL_CONFIG_TEMPLATE = """\
SIMPLE=1
NODECALL=N0CALL
NODEALIAS=TEST
LOCATOR=NONE
AGWPORT=$agw_port

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
 ID=KissSerial
 TYPE=ASYNC
 PROTOCOL=KISS
 COMPORT=__SLAVE__
 SPEED=9600
ENDPORT
"""


def _encode_ax25_call(call: str, ssid: int = 0, last: bool = True) -> bytes:
    """Pack ``call`` (left-justified to 6 chars) into AX.25 wire form."""
    padded = call.ljust(6).upper().encode("ascii")[:6]
    out = bytearray(b << 1 for b in padded)
    ssid_byte = 0x60 | ((ssid & 0x0F) << 1) | (1 if last else 0)
    out.append(ssid_byte)
    return bytes(out)


def _ax25_ui_frame(src: str, dest: str, body: bytes) -> bytes:
    """Build a complete AX.25 UI frame: dest + src + CTL=UI + PID=F0 + body."""
    return (
        _encode_ax25_call(dest, last=False)
        + _encode_ax25_call(src, last=True)
        + bytes([0x03, 0xF0])
        + body
    )


def test_linbpq_opens_pty_as_serial_kiss_port(tmp_path: Path):
    """linbpq's serial driver opens the PTY slave node successfully."""
    with PtyKissModem() as modem:
        cfg = Template(KISS_SERIAL_CONFIG_TEMPLATE.replace("__SLAVE__", modem.slave_path))
        with LinbpqInstance(tmp_path, config_template=cfg):
            # If we got here, linbpq booted (the fixture's readiness
            # probe checks the telnet port). Now look at the log for
            # the ASYNC port-init line.
            log = (tmp_path / "linbpq.stdout.log").read_bytes()
    assert b"ASYNC" in log, f"no ASYNC port init in log: {log[-500:]!r}"
    assert modem.slave_path.encode() in log, (
        f"slave path {modem.slave_path} not in log: {log[-500:]!r}"
    )


def test_kiss_serial_ax25_frame_lands_in_mh(tmp_path: Path):
    """A KISS-framed AX.25 UI frame written to the master end of the
    PTY shows up in MH on the corresponding port."""
    with PtyKissModem() as modem:
        cfg = Template(KISS_SERIAL_CONFIG_TEMPLATE.replace("__SLAVE__", modem.slave_path))
        with LinbpqInstance(tmp_path, config_template=cfg) as linbpq:
            # Send a UI frame from G7TEST to NODES with a body.
            ax25 = _ax25_ui_frame("G7TEST", "NODES", b"HELLO from G7TEST")
            modem.write(kiss_encode(ax25))
            # Give linbpq a moment to ingest.
            time.sleep(1.0)

            with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
                client.login("test", "test")
                response = client.run_command("MH 2")
    assert b"G7TEST" in response, (
        f"G7TEST not heard on port 2: {response!r}"
    )
    assert b"Heard List for Port 2" in response


def test_pty_ui_frame_visible_via_agw_monitor(tmp_path: Path):
    """An AGW client with monitor-mode toggled on receives a 'U'
    (UI) monitor frame summarising a UI frame that arrived on the
    serial KISS port — exercises both transports end-to-end."""
    from helpers.agw_client import AgwClient, AgwFrame

    with PtyKissModem() as modem:
        cfg = Template(
            KISS_SERIAL_CONFIG_TEMPLATE.replace("__SLAVE__", modem.slave_path)
        )
        with LinbpqInstance(tmp_path, config_template=cfg) as linbpq:
            with AgwClient("127.0.0.1", linbpq.agw_port, timeout=3) as agw:
                # Toggle monitor on — no reply expected.
                agw.send(AgwFrame(0, b"m", 0, b"", b"", b""))

                # Send a UI frame on the serial port.
                ax25 = _ax25_ui_frame("G7TEST", "NODES", b"hello")
                modem.write(kiss_encode(ax25))
                time.sleep(1.0)

                reply = agw.recv()

    assert reply.data_kind == b"U", (
        f"expected 'U' UI-monitor frame, got {reply.data_kind!r}"
    )
    text = reply.data.decode("ascii", errors="replace")
    assert "G7TEST" in text, f"src not in monitor text: {text!r}"
    assert "NODES" in text, f"dest not in monitor text: {text!r}"
    assert "hello" in text, f"payload not in monitor text: {text!r}"


def test_kiss_serial_cq_beacon_lands_on_pty(tmp_path: Path):
    """``LISTEN 2`` then ``CQ`` causes linbpq to transmit a UI beacon
    out the serial KISS port; the test reads the master end of the
    PTY and parses out a real KISS-framed AX.25 UI frame with the
    configured NODECALL as the source and ``CQ`` as the destination."""
    with PtyKissModem() as modem:
        cfg = Template(KISS_SERIAL_CONFIG_TEMPLATE.replace("__SLAVE__", modem.slave_path))
        with LinbpqInstance(tmp_path, config_template=cfg) as linbpq:
            # Drain anything queued during init.
            modem.read_available()

            with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
                client.login("test", "test")
                client.run_command("LISTEN 2")
                client.run_command("CQ")

            # Give the TX a beat.
            time.sleep(0.5)
            tx = modem.read_available()

    assert tx, "no bytes from linbpq after CQ"
    frames = kiss_decode_frames(tx)
    assert frames, f"no KISS frames decoded: {tx.hex()}"

    # First frame: dest (CQ), src (N0CALL-something), then CTL+PID
    frame = frames[0]
    assert len(frame) >= 14, f"frame too short for AX.25 header: {frame.hex()}"
    dest = ax25_decode_call(frame[:7])
    src = ax25_decode_call(frame[7:14])
    ctl = frame[14] if len(frame) > 14 else None
    pid = frame[15] if len(frame) > 15 else None

    assert dest == "CQ", f"unexpected dest call: {dest!r} (frame {frame.hex()})"
    assert src.startswith("N0CALL"), (
        f"unexpected src call: {src!r} (frame {frame.hex()})"
    )
    assert ctl == 0x03, f"expected UI CTL=0x03, got {ctl!r}"
    assert pid == 0xF0, f"expected PID=0xF0 (no L3), got {pid!r}"
