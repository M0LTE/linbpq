"""Two-instance AGW binary-transparency tests.

Deployment shape we exercise:

    App-A ─AGW── BPQ-A ──AX/IP-UDP── BPQ-B ──AGW── App-B

Both apps are AGW clients.  Each BPQ has the dialed callsign
declared as an ``APPLICATION`` (so ``APPL1CALL`` is the call the
peer expects to reach), the matching cross-MAP entry on the
remote AXIP driver (so the AX.25 SABM from the peer's side is
sent over UDP to this instance), and ``AGWSESSIONS`` /
``AGWMASK`` set so AGW pre-allocates listening streams that
catch incoming connects to the APPL slot.

App-A initiates an AGW connect from its registered call to
App-B's APPL1CALL on the AXIP port.  BPQ-A constructs an
AX.25 SABM, sends it via the AXIP MAP to BPQ-B's UDP socket;
BPQ-B sees the inbound SABM addressed to its APPL1CALL,
finds the AGW-listening stream registered with that call, and
delivers the connect to App-B.  Both apps see a 'C' confirm.

After the connect, App-A sends 'D' frames; BPQ-A puts the
bytes onto the AX.25 connection over AXIP; BPQ-B delivers
them to App-B as 'D' frames on its AGW socket.  AGW's data
records carry an explicit DataLength header — there's no
in-band escape that could mangle a byte — so this is the
binary-transparent path the apps interface is documented for.

Per project policy we don't fix in C; if a byte mangles, we
file an issue.  The single-instance variant of this test
already turned up M0LTE/linbpq#24 (CR → CR-LF expansion on
the BPQ-side CMDPORT relay) — that bug doesn't apply here
because we don't go through CMDPORT.
"""

from __future__ import annotations

import socket
import time
from contextlib import ExitStack
from pathlib import Path
from string import Template

import pytest

from helpers.agw_client import AgwClient, AgwFrame
from helpers.linbpq_instance import LinbpqInstance


# Config: each side has an APPLICATION with a unique callsign,
# AGWSESSIONS / AGWMASK so AGW pre-allocates listening streams
# (without these the inbound SABM goes nowhere — see
# AGWAPI.c::SetUpHostSessions), plus an AXIP MAP for the peer's
# APPL call so SABMs leave the local instance.
_PEER_AGW_CFG = Template(
    """\
SIMPLE=1
NODECALL=$node_call
NODEALIAS=$node_alias
LOCATOR=NONE
NODESINTERVAL=1
AGWPORT=$agw_port
AGWSESSIONS=10
AGWMASK=1
APPLICATIONS=$appl_alias
APPL1CALL=$appl_call
APPL1ALIAS=$appl_alias

PORT
 ID=Telnet
 DRIVER=Telnet
 CONFIG
 TCPPORT=$telnet_port
 HTTPPORT=$http_port
 NETROMPORT=$netrom_port
 FBBPORT=$fbb_port
 APIPORT=$api_port
 MAXSESSIONS=20
 USER=test,test,$node_call,,SYSOP
ENDPORT

PORT
 ID=AXIP
 DRIVER=BPQAXIP
 QUALITY=200
 MINQUAL=1
 CONFIG
 UDP $axip_port
 BROADCAST NODES
 MAP $peer_call 127.0.0.1 UDP $peer_axip_port B
 MAP $peer_appl_call 127.0.0.1 UDP $peer_axip_port B
ENDPORT

ROUTES:
$peer_call,200,2
***
"""
)


def _peer_template(*, node_call, node_alias, peer_call, peer_axip_port,
                   appl_call, appl_alias, peer_appl_call):
    base = _PEER_AGW_CFG.template

    class _T(Template):
        def substitute(self, **kw):
            return Template.substitute(
                self,
                node_call=node_call,
                node_alias=node_alias,
                peer_call=peer_call,
                peer_axip_port=peer_axip_port,
                appl_call=appl_call,
                appl_alias=appl_alias,
                peer_appl_call=peer_appl_call,
                **kw,
            )

    return _T(base)


# AGW port indexing: AGW port 0 → BPQ port 1 (Telnet); AGW port
# 1 → BPQ port 2 (AXIP).  The AXIP-port path is what makes the
# SABM travel between BPQ-A and BPQ-B.
AGW_AXIP_PORT_INDEX = 1


# Distinct callsigns so test failures aren't ambiguous.  A's
# APPL is N0AAA-9; B's is N0BBB-9.
A_APPL_CALL = "N0AAA-9"
B_APPL_CALL = "N0BBB-9"


@pytest.fixture
def two_instance_agw(tmp_path: Path):
    """Two BPQs over AXIP-UDP, each with AGW + APPLICATION binding.

    Yields ``(a, b)`` — both ``LinbpqInstance``s, started.  AGW
    is at ``a.agw_port`` / ``b.agw_port``.
    """
    a_dir = tmp_path / "A"
    b_dir = tmp_path / "B"
    a_dir.mkdir()
    b_dir.mkdir()

    a = LinbpqInstance(
        a_dir,
        config_template=_peer_template(
            node_call="N0AAA",
            node_alias="AAA",
            peer_call="N0BBB",
            peer_axip_port=0,
            appl_call=A_APPL_CALL,
            appl_alias="APPLA",
            peer_appl_call=B_APPL_CALL,
        ),
    )
    b = LinbpqInstance(
        b_dir,
        config_template=_peer_template(
            node_call="N0BBB",
            node_alias="BBB",
            peer_call="N0AAA",
            peer_axip_port=a.axip_port,
            appl_call=B_APPL_CALL,
            appl_alias="APPLB",
            peer_appl_call=A_APPL_CALL,
        ),
    )
    a.config_template = _peer_template(
        node_call="N0AAA",
        node_alias="AAA",
        peer_call="N0BBB",
        peer_axip_port=b.axip_port,
        appl_call=A_APPL_CALL,
        appl_alias="APPLA",
        peer_appl_call=B_APPL_CALL,
    )

    with ExitStack() as stack:
        a.start(ready_timeout=15.0)
        stack.callback(_safe_stop, a)
        b.start(ready_timeout=15.0)
        stack.callback(_safe_stop, b)
        time.sleep(1.0)
        yield a, b


def _safe_stop(linbpq: LinbpqInstance) -> None:
    try:
        if linbpq.proc:
            linbpq.proc.terminate()
            linbpq.proc.wait(timeout=5)
    except Exception:
        if linbpq.proc:
            linbpq.proc.kill()


# ── AGW helpers ──────────────────────────────────────────────────


def _register(client: AgwClient, callsign: str) -> None:
    client.send(
        AgwFrame(
            port=0,
            data_kind=b"X",
            pid=0,
            callfrom=callsign.encode("ascii"),
            callto=b"",
            data=b"",
        )
    )
    reply = client.recv()
    assert reply.data_kind == b"X" and reply.data == b"\x01", (
        f"AGW register {callsign!r} failed: {reply!r}"
    )


def _connect(client: AgwClient, port_index: int, callfrom: str, callto: str) -> None:
    client.send(
        AgwFrame(
            port=port_index,
            data_kind=b"C",
            pid=0,
            callfrom=callfrom.encode("ascii"),
            callto=callto.encode("ascii"),
            data=b"",
        )
    )


def _wait_for_kind(
    client: AgwClient, kind: bytes, timeout: float = 10.0
) -> AgwFrame:
    """Read AGW frames until one with ``data_kind == kind`` arrives."""
    deadline = time.monotonic() + timeout
    client.sock.settimeout(0.5)
    while time.monotonic() < deadline:
        try:
            frame = client.recv()
        except (TimeoutError, socket.timeout):
            continue
        if frame.data_kind == kind:
            return frame
        if frame.data_kind == b"d":
            raise RuntimeError(f"got disconnect while waiting for {kind!r}: {frame!r}")
    raise TimeoutError(f"no AGW {kind!r} frame within {timeout}s")


def _send_data(
    client: AgwClient, port_index: int, callfrom: str, callto: str, data: bytes
) -> None:
    client.send(
        AgwFrame(
            port=port_index,
            data_kind=b"D",
            pid=0xF0,
            callfrom=callfrom.encode("ascii"),
            callto=callto.encode("ascii"),
            data=data,
        )
    )


def _drain_data(
    client: AgwClient, expected_min: int, timeout: float = 8.0
) -> bytes:
    """Read AGW frames until ``expected_min`` bytes of 'D' data
    have accumulated, or timeout.  Returns the concatenated
    payload; ignores other frame kinds.
    """
    deadline = time.monotonic() + timeout
    payload = b""
    client.sock.settimeout(0.5)
    while time.monotonic() < deadline and len(payload) < expected_min:
        try:
            frame = client.recv()
        except (TimeoutError, socket.timeout):
            continue
        if frame.data_kind == b"D":
            payload += frame.data
        elif frame.data_kind == b"d":
            break
    # Brief drain for any trailing data.
    client.sock.settimeout(0.5)
    deadline2 = time.monotonic() + 1.0
    while time.monotonic() < deadline2:
        try:
            frame = client.recv()
        except (TimeoutError, socket.timeout):
            break
        if frame.data_kind == b"D":
            payload += frame.data
    return payload


def _establish_session(a: LinbpqInstance, b: LinbpqInstance) -> tuple[AgwClient, AgwClient]:
    """Open AGW clients on both sides, register the APPL calls,
    initiate the connect, wait for both 'C' confirms.  Returns
    ``(app_a, app_b)`` ready for ``_send_data`` / ``_drain_data``.
    """
    app_a = AgwClient("127.0.0.1", a.agw_port, timeout=15)
    app_b = AgwClient("127.0.0.1", b.agw_port, timeout=15)

    _register(app_a, A_APPL_CALL)
    _register(app_b, B_APPL_CALL)

    _connect(app_a, AGW_AXIP_PORT_INDEX, A_APPL_CALL, B_APPL_CALL)

    # Both sides should see a 'C' confirm.
    confirm_a = _wait_for_kind(app_a, b"C", timeout=10.0)
    confirm_b = _wait_for_kind(app_b, b"C", timeout=10.0)
    assert b"CONNECTED" in confirm_a.data.upper(), confirm_a
    assert b"CONNECTED" in confirm_b.data.upper(), confirm_b
    return app_a, app_b


# ── Tests ────────────────────────────────────────────────────────


def test_agw_two_instance_connect_establishes(two_instance_agw):
    """Smoke: AGW connect from A's APPL call to B's APPL call
    over the AXIP carrier produces 'C' confirms on both sides."""
    a, b = two_instance_agw
    app_a, app_b = _establish_session(a, b)
    app_a.close()
    app_b.close()


def test_agw_two_instance_data_round_trip(two_instance_agw):
    """A 'D' record from App-A appears at App-B unchanged."""
    a, b = two_instance_agw
    app_a, app_b = _establish_session(a, b)
    try:
        payload = b"Hello two-instance AGW tunnel"
        _send_data(
            app_a, AGW_AXIP_PORT_INDEX, A_APPL_CALL, B_APPL_CALL, payload
        )
        received = _drain_data(app_b, expected_min=len(payload), timeout=8.0)
    finally:
        app_a.close()
        app_b.close()
    assert received == payload, (
        f"data mangled: sent {payload!r}, received {received!r}"
    )


@pytest.mark.parametrize(
    "byte_value,name",
    [
        (0x00, "NUL"),
        (0x01, "SOH"),
        (0x07, "BEL"),
        (0x08, "BS"),
        (0x09, "TAB"),
        (0x0A, "LF"),
        (0x0D, "CR"),
        (0x1A, "Ctrl-Z"),
        (0x1B, "ESC"),
        (0x7F, "DEL"),
        (0x80, "high-bit"),
        (0xFE, "0xFE"),
        (0xFF, "0xFF"),
    ],
)
def test_agw_two_instance_byte_transparency(
    two_instance_agw, byte_value, name
):
    """Each interesting byte value through the AGW two-instance
    tunnel must arrive at the peer byte-perfect.  AGW's 'D'
    records carry an explicit DataLength header — there's no
    in-band escape that could mangle a byte — so this is the
    binary-transparent path.  Any failure here is a real bug."""
    a, b = two_instance_agw
    app_a, app_b = _establish_session(a, b)
    sentinel = bytes([0x41, byte_value, 0x5A])
    try:
        _send_data(
            app_a, AGW_AXIP_PORT_INDEX, A_APPL_CALL, B_APPL_CALL, sentinel
        )
        received = _drain_data(app_b, expected_min=3, timeout=4.0)
    finally:
        app_a.close()
        app_b.close()

    if b"A" not in received or b"Z" not in received[received.index(b"A") + 1:]:
        pytest.fail(
            f"sentinel A<0x{byte_value:02X} {name}>Z not received intact "
            f"via AGW two-instance tunnel.  Got: {received!r}"
        )
    a_idx = received.index(b"A")
    z_idx = received.index(b"Z", a_idx + 1)
    middle = received[a_idx + 1:z_idx]
    assert middle == bytes([byte_value]), (
        f"byte 0x{byte_value:02X} ({name}) mangled in AGW two-instance "
        f"tunnel.  Sent A<0x{byte_value:02X}>Z, received A<{middle!r}>Z"
    )


def test_agw_two_instance_full_byte_sweep(two_instance_agw):
    """All 256 byte values 0x00..0xFF in a single 'D' record
    must arrive at the peer byte-perfect."""
    a, b = two_instance_agw
    app_a, app_b = _establish_session(a, b)
    payload = bytes(range(256))
    try:
        _send_data(
            app_a, AGW_AXIP_PORT_INDEX, A_APPL_CALL, B_APPL_CALL, payload
        )
        received = _drain_data(
            app_b, expected_min=len(payload), timeout=10.0
        )
    finally:
        app_a.close()
        app_b.close()

    if received == payload:
        return

    n = min(len(payload), len(received))
    diffs = [
        (i, payload[i], received[i])
        for i in range(n)
        if payload[i] != received[i]
    ]
    if diffs:
        sample = ", ".join(
            f"idx {i}: sent 0x{s:02X} got 0x{g:02X}" for i, s, g in diffs[:8]
        )
        pytest.fail(
            f"{len(diffs)}/{n} bytes mangled in AGW two-instance sweep.  "
            f"First few: {sample}.  "
            f"Sent {len(payload)} bytes, received {len(received)} bytes."
        )
    pytest.fail(
        f"length mismatch: sent {len(payload)}, got {len(received)}"
    )


def test_agw_two_instance_burst_ordering_chunked(two_instance_agw):
    """1024 bytes (256 four-byte big-endian counters) round-trip
    in order through the AGW two-instance tunnel, chunked into
    per-record payloads ≤ PACLEN.

    AGW silently drops `D` records larger than PACLEN
    (M0LTE/linbpq#40), so a single 1024-byte 'D' frame fails.
    Chunked into 64-byte sends (16 chunks × 64 = 1024 bytes
    total), the data round-trips cleanly and ordering is
    preserved across records.
    """
    import struct

    a, b = two_instance_agw
    app_a, app_b = _establish_session(a, b)
    chunks = [struct.pack(">I", i) for i in range(256)]
    payload = b"".join(chunks)
    chunk_size = 64  # well under default PACLEN of 256
    try:
        for off in range(0, len(payload), chunk_size):
            _send_data(
                app_a,
                AGW_AXIP_PORT_INDEX,
                A_APPL_CALL,
                B_APPL_CALL,
                payload[off:off + chunk_size],
            )
            time.sleep(0.05)  # let the receiver drain between sends
        received = _drain_data(
            app_b, expected_min=len(payload), timeout=20.0
        )
    finally:
        app_a.close()
        app_b.close()

    assert len(received) == len(payload), (
        f"length mismatch: sent {len(payload)}, got {len(received)}"
    )
    for i in range(256):
        chunk = received[i * 4:(i + 1) * 4]
        (got,) = struct.unpack(">I", chunk)
        assert got == i, (
            f"counter at offset {i * 4}: expected {i}, got {got}"
        )


@pytest.mark.xfail(
    reason="M0LTE/linbpq#40: AGW silently drops D records > PACLEN "
           "(default 256), then resets the socket on subsequent sends",
    strict=True,
)
def test_agw_two_instance_oversized_record_handling(two_instance_agw):
    """A single 'D' record larger than the negotiated PACLEN
    should either fragment internally or fail loudly.  Today it
    silently drops the data and leaves the socket in a broken
    state — see M0LTE/linbpq#40.

    xfail strict so when #40 is fixed (either fragmentation or
    a loud error frame) this test starts passing automatically.
    """
    a, b = two_instance_agw
    app_a, app_b = _establish_session(a, b)
    payload = bytes((i & 0xFF) for i in range(512))
    try:
        _send_data(
            app_a, AGW_AXIP_PORT_INDEX, A_APPL_CALL, B_APPL_CALL, payload
        )
        received = _drain_data(
            app_b, expected_min=len(payload), timeout=10.0
        )
    finally:
        app_a.close()
        app_b.close()
    assert received == payload, (
        f"oversized record not delivered: sent {len(payload)} bytes, "
        f"got {len(received)} bytes"
    )
