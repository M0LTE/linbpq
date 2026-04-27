"""NET/ROM-over-TCP framing helpers for tests.

Wire format (NETROMTCP.c:27):

    Length (2 bytes little-endian) | Call (10 bytes ASCII) |
    PID (1 byte = 0xCF) | NETROM L3/L4 packet

``Length`` includes the 2-byte length field itself.  ``Call`` is the
neighbour's text callsign, NUL-padded to 10 bytes.  ``PID`` is 0xCF
(the NET/ROM protocol ID) — used by linbpq as a framing-error check.
"""

from __future__ import annotations

import struct


def encode_ax25_call(call: str, ssid: int = 0, last: bool = False) -> bytes:
    """Pack ``call`` (left-justified to 6 chars) into AX.25 wire form
    (6 left-shifted ASCII bytes + SSID byte)."""
    padded = call.ljust(6).upper().encode("ascii")[:6]
    out = bytearray(b << 1 for b in padded)
    out.append(0x60 | ((ssid & 0x0F) << 1) | (1 if last else 0))
    return bytes(out)


def build_nrtcp_frame(call: str, l3_packet: bytes) -> bytes:
    """Build a complete NET/ROM-over-TCP wire frame."""
    call_bytes = call.encode("ascii").ljust(10, b"\x00")[:10]
    body = call_bytes + b"\xCF" + l3_packet
    length = len(body) + 2  # +2 for the length field itself
    return struct.pack("<H", length) + body


def build_l3_drop_packet(
    src_call: str = "N0FAKE",
    dest_call: str = "NOWHERE",
) -> bytes:
    """A NET/ROM L3 packet with TTL=1: linbpq decrements to 0 and
    drops the frame harmlessly (L4Code.c:188).  A safe minimal
    payload for tests that want to drive the FindNeighbour /
    framing-validation path without actually causing routing
    side-effects."""
    return (
        encode_ax25_call(src_call)
        + encode_ax25_call(dest_call)
        + bytes([1])  # L3TTL
        + bytes(5)    # L4 header (zeros — gets dropped before L4 dispatch)
    )
