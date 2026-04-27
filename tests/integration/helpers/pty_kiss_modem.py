"""PTY-backed fake KISS modem for tests.

Stands in for a serial-attached KISS modem (the kind linbpq talks
to via ``TYPE=ASYNC PROTOCOL=KISS COMPORT=/dev/tty… SPEED=…``).

Usage:

    with PtyKissModem() as modem:
        # configure linbpq with COMPORT=modem.slave_path
        # start linbpq
        # modem.master_fd is the master end of the pty — read what
        # linbpq writes, write back what we want it to receive.

KISS framing: FEND (0xC0) delimits frames; FESC (0xDB) is the
escape; TFEND (0xDC) and TFESC (0xDD) are the escaped forms of
FEND / FESC inside a frame.  A frame's first byte is a command
byte where the upper nybble is the port number (we use 0) and the
lower nybble is the KISS command (0 = data).
"""

from __future__ import annotations

import os


FEND = 0xC0
FESC = 0xDB
TFEND = 0xDC
TFESC = 0xDD


def kiss_decode_frames(stream: bytes) -> list[bytes]:
    """Split ``stream`` on FEND, unescape FESC sequences in each
    frame, drop the leading command byte, return AX.25 payloads
    (just the AX.25 frame, no KISS framing or command byte)."""
    frames: list[bytes] = []
    for chunk in stream.split(bytes([FEND])):
        if not chunk:
            continue
        # Unescape FESC sequences.
        out = bytearray()
        i = 0
        while i < len(chunk):
            b = chunk[i]
            if b == FESC and i + 1 < len(chunk):
                nxt = chunk[i + 1]
                if nxt == TFEND:
                    out.append(FEND)
                elif nxt == TFESC:
                    out.append(FESC)
                else:
                    out.extend([FESC, nxt])
                i += 2
            else:
                out.append(b)
                i += 1
        if len(out) >= 1:
            # Drop the KISS command byte; payload is what follows.
            frames.append(bytes(out[1:]))
    return frames


def ax25_decode_call(seven_bytes: bytes) -> str:
    """Render a 6-byte left-shifted call + SSID byte back to text."""
    if len(seven_bytes) < 7:
        return ""
    chars = bytes(b >> 1 for b in seven_bytes[:6]).decode(
        "ascii", errors="replace"
    ).rstrip()
    ssid = (seven_bytes[6] >> 1) & 0x0F
    return f"{chars}-{ssid}" if ssid else chars


def kiss_encode(data: bytes, port: int = 0, cmd: int = 0) -> bytes:
    """Wrap ``data`` in a KISS data frame for ``port``."""
    cmd_byte = ((port & 0x0F) << 4) | (cmd & 0x0F)
    out = bytearray([FEND, cmd_byte])
    for b in data:
        if b == FEND:
            out += bytes([FESC, TFEND])
        elif b == FESC:
            out += bytes([FESC, TFESC])
        else:
            out.append(b)
    out.append(FEND)
    return bytes(out)


class PtyKissModem:
    """Open a PTY pair; the slave path is what linbpq sees as a
    serial device."""

    def __init__(self):
        self.master_fd: int = -1
        self.slave_path: str = ""

    def __enter__(self) -> "PtyKissModem":
        self.master_fd, slave_fd = os.openpty()
        self.slave_path = os.ttyname(slave_fd)
        # We don't keep the slave fd open in our process — linbpq
        # will open the path itself.  But on Linux, closing the
        # slave fd before the path is opened-by-someone-else can
        # cause the master to see EIO; keeping it open until linbpq
        # has had a chance to open() the slave path is safer.
        # The caller is expected to start linbpq quickly after
        # entering this context.
        self._slave_fd = slave_fd
        return self

    def __exit__(self, *_exc) -> None:
        for fd in (self._slave_fd, self.master_fd):
            try:
                os.close(fd)
            except OSError:
                pass

    def read_available(self, max_bytes: int = 4096) -> bytes:
        """Non-blocking read of whatever's queued from linbpq."""
        os.set_blocking(self.master_fd, False)
        try:
            try:
                return os.read(self.master_fd, max_bytes)
            except BlockingIOError:
                return b""
        finally:
            os.set_blocking(self.master_fd, True)

    def write(self, data: bytes) -> None:
        os.write(self.master_fd, data)
