"""Phase 2 — AGW TCP: version handshake + richer command coverage."""

from __future__ import annotations

from helpers.agw_client import AgwClient, AgwFrame, request_version


def test_agw_version_request(linbpq):
    """Sending an 'R' frame returns the AGW version constants from AGWAPI.c."""
    major, minor = request_version("127.0.0.1", linbpq.agw_port)
    # AGWAPI.c hard-codes AGWVersion = {2003, 999}; lock that in so any
    # change is intentional.
    assert (major, minor) == (2003, 999), (
        f"unexpected AGW version: {major}.{minor}"
    )


def test_agw_get_ports_lists_telnet(linbpq):
    """``G`` returns a semicolon-separated port description; the
    Telnet port we configured shows up."""
    with AgwClient("127.0.0.1", linbpq.agw_port) as client:
        client.send(AgwFrame(0, b"G", 0, b"", b"", b""))
        reply = client.recv()
    assert reply.data_kind == b"G", f"expected G reply, got {reply.data_kind!r}"
    assert b"Telnet" in reply.data, (
        f"Telnet port not in port list: {reply.data!r}"
    )


def test_agw_get_port_caps_returns_12_bytes(linbpq):
    """``g`` returns the per-port capabilities block."""
    with AgwClient("127.0.0.1", linbpq.agw_port) as client:
        client.send(AgwFrame(0, b"g", 0, b"", b"", b""))
        reply = client.recv()
    assert reply.data_kind == b"g"
    # AGWAPI.c hard-codes a 12-byte AGWPortCaps array.
    assert len(reply.data) == 12, (
        f"expected 12-byte caps payload, got {len(reply.data)}: {reply.data!r}"
    )


def test_agw_register_callsign_returns_success(linbpq):
    """``X`` registers a callsign on the AGW connection — the BPQ
    emulator accepts any call (including repeats and malformed
    callsigns) and replies 0x01 success."""
    with AgwClient("127.0.0.1", linbpq.agw_port) as client:
        # First registration.
        client.send(AgwFrame(0, b"X", 0, b"N0TEST", b"", b""))
        reply = client.recv()
        assert reply.data_kind == b"X"
        assert reply.data == b"\x01", f"expected 0x01, got {reply.data!r}"

        # Repeating the same registration — still 0x01.
        client.send(AgwFrame(0, b"X", 0, b"N0TEST", b"", b""))
        reply = client.recv()
        assert reply.data == b"\x01"
