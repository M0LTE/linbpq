"""Two-instance binary-transparency tests for the apps tunnel.

Deployment shape we exercise:

    App-A ─FBB──┐                                    ┌── App-B (CMDPORT app)
                │                                    │
                BPQ-A ──AX/IP-UDP── BPQ-B ──CMDPORT──┘

App-A is an FBB host-mode client (the 8-bit-clean BPQ listener
— see ``test_apps_interface_transparency.py``).  It logs in,
issues ``C 2 N0BBB`` to connect to the peer node over AXIP-UDP,
then ``C 1 HOST 0`` to dial BPQ-B's CMDPORT[0] which is
App-B's TCP listener.  After both hops, every byte App-A
writes flows:

    FBB → BPQ-A → AX.25/AXIP-UDP → BPQ-B → CMDPORT relay → App-B

AX.25 / AXIP-UDP is binary by construction; any mangling
beyond the known CMDPORT bug (M0LTE/linbpq#24, CR → CR-LF
expansion on the BPQ-side CMDPORT relay) would be a new
finding in the AX.25 carrier.

We tried AGW for the App-A side first.  AGW is the documented
"binary-transparent" path, but its outbound connect requires
an APPLICATION binding for the destination call to fire the 'C'
confirm reliably; in our minimal-cfg test topology that didn't
complete.  FBB host mode is functionally equivalent for what
we're measuring (binary-clean user-to-BPQ transport) and
proves out without the extra plumbing.
"""

from __future__ import annotations

import socket
import time
from contextlib import ExitStack, contextmanager
from pathlib import Path
from string import Template

import pytest

from helpers.cmdport_app import CmdportApp
from helpers.linbpq_instance import LinbpqInstance


# Two-instance config with AGW + CMDPORT on each side.  The MAP
# already routes between the two NODECALLs (N0AAA ↔ N0BBB) over
# UDP loopback.  We don't need extra MAPs because App-A's AGW
# connects to N0BBB (the peer's node call), and that's already
# in the existing MAP table.
_PEER_AGW_CMD_CFG = Template(
    """\
SIMPLE=1
NODECALL=$node_call
NODEALIAS=$node_alias
LOCATOR=NONE
NODESINTERVAL=1
AGWPORT=$agw_port

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
 CMDPORT $cmd_app_port
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
ENDPORT

ROUTES:
$peer_call,200,2
***
"""
)


def _peer_template(*, node_call, node_alias, peer_call, peer_axip_port, cmd_app_port):
    base = _PEER_AGW_CMD_CFG.template

    class _T(Template):
        def substitute(self, **kw):
            return Template.substitute(
                self,
                node_call=node_call,
                node_alias=node_alias,
                peer_call=peer_call,
                peer_axip_port=peer_axip_port,
                cmd_app_port=cmd_app_port,
                **kw,
            )

    return _T(base)


@pytest.fixture
def two_instance_agw_cmdport(tmp_path: Path):
    """Two BPQs over AXIP-UDP, each with AGW and a CMDPORT app.

    Yields ``(a, b, app_a, app_b)`` — both ``LinbpqInstance``s
    plus their respective ``CmdportApp`` listeners.  ``app_b``
    is the one the binary tunnel terminates on; ``app_a`` exists
    for symmetry but our tests only use ``app_b``.
    """
    a_dir = tmp_path / "A"
    b_dir = tmp_path / "B"
    a_dir.mkdir()
    b_dir.mkdir()

    with ExitStack() as stack:
        cm_app_a = stack.enter_context(_cm_app())
        cm_app_b = stack.enter_context(_cm_app())

        a = LinbpqInstance(
            a_dir,
            config_template=_peer_template(
                node_call="N0AAA",
                node_alias="AAA",
                peer_call="N0BBB",
                peer_axip_port=0,
                cmd_app_port=cm_app_a.port,
            ),
        )
        b = LinbpqInstance(
            b_dir,
            config_template=_peer_template(
                node_call="N0BBB",
                node_alias="BBB",
                peer_call="N0AAA",
                peer_axip_port=a.axip_port,
                cmd_app_port=cm_app_b.port,
            ),
        )
        a.config_template = _peer_template(
            node_call="N0AAA",
            node_alias="AAA",
            peer_call="N0BBB",
            peer_axip_port=b.axip_port,
            cmd_app_port=cm_app_a.port,
        )

        a.start(ready_timeout=15.0)
        stack.callback(_safe_stop, a)
        b.start(ready_timeout=15.0)
        stack.callback(_safe_stop, b)
        time.sleep(1.0)
        yield a, b, cm_app_a, cm_app_b


@contextmanager
def _cm_app():
    app = CmdportApp()
    try:
        yield app
    finally:
        app.close()


def _safe_stop(linbpq: LinbpqInstance) -> None:
    try:
        if linbpq.proc:
            linbpq.proc.terminate()
            linbpq.proc.wait(timeout=5)
    except Exception:
        if linbpq.proc:
            linbpq.proc.kill()


# ── Tunnel setup ─────────────────────────────────────────────────


def _open_tunnel(
    a: LinbpqInstance, b: LinbpqInstance, app_b: CmdportApp
) -> socket.socket:
    """Establish the full chain end-to-end via FBB host mode.

    Why FBB instead of AGW: AGW initiates connects via an
    asynchronous 'C' confirm that requires the node prompt to
    cooperatively complete the handshake.  In our test
    topology that handshake doesn't fire reliably (likely
    because the AGW path expects an APPLICATION binding for
    the destination).  FBB host mode is the same 8-bit-clean
    listener the single-instance test uses (see
    ``test_apps_interface_transparency.py``) and the only
    binary-transparency-relevant differences are upstream of
    BPQ-A — the back-half of the chain (AX/IP carrier + BPQ-B
    relay to CMDPORT) is identical.

    Returns the open FBB socket, ready for binary writes.
    """
    sock = socket.create_connection(
        ("127.0.0.1", a.fbb_port), timeout=15
    )
    sock.settimeout(2.0)

    # FBB login is silent — send creds and wait for the prompt.
    sock.sendall(b"test\r")
    time.sleep(0.2)
    sock.sendall(b"test\r")
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        try:
            data = sock.recv(4096)
        except (TimeoutError, socket.timeout):
            continue
        if not data:
            raise RuntimeError("FBB login closed prematurely")
        if b"TEST:N0AAA}" in data:
            break

    # Connect to N0BBB over AXIP (port 2).
    sock.sendall(b"C 2 N0BBB\r")
    deadline = time.monotonic() + 8.0
    saw_connect = False
    while time.monotonic() < deadline:
        try:
            data = sock.recv(4096)
        except (TimeoutError, socket.timeout):
            continue
        if not data:
            break
        if b"Connected to" in data or b"BBB}" in data:
            saw_connect = True
            break
    if not saw_connect:
        sock.close()
        raise RuntimeError(
            "C 2 N0BBB didn't reach the peer over AX/IP-UDP "
            "(check both daemons are up + AXIP MAP is set)"
        )

    # Now we're at B's node prompt.  Dial B's CMDPORT[0].
    sock.sendall(b"C 1 HOST 0\r")
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        try:
            data = sock.recv(4096)
        except (TimeoutError, socket.timeout):
            continue
        if not data:
            break
        if b"Connected to APPL" in data or b"APPL\r" in data:
            break

    if not app_b.wait_for_client(timeout=5.0):
        sock.close()
        raise RuntimeError(
            "App-B's CMDPORT didn't receive the inbound dial — "
            "the tunnel didn't establish."
        )
    # Drain the calling-station banner from app_b so subsequent
    # recv()s only see test-driver payload.
    intro = app_b.recv(timeout=2.0)
    assert b"N0AAA" in intro, (
        f"expected N0AAA banner from B's CMDPORT, got {intro!r}"
    )

    return sock


def _drain_app(
    app: CmdportApp, expected_min: int, total_timeout: float = 8.0
) -> bytes:
    """Read from CMDPORT app until ``expected_min`` bytes arrive
    or ``total_timeout`` elapses + 1.5 s of silence after data."""
    buf = b""
    deadline = time.monotonic() + total_timeout
    last_grew = time.monotonic()
    while time.monotonic() < deadline:
        if len(buf) >= expected_min:
            extra = app.recv(timeout=0.5)
            if extra:
                buf += extra
                last_grew = time.monotonic()
            else:
                break
        chunk = app.recv(timeout=0.5)
        if chunk:
            buf += chunk
            last_grew = time.monotonic()
        elif time.monotonic() - last_grew > 1.5 and buf:
            break
    return buf


# ── Tests ────────────────────────────────────────────────────────


def test_two_instance_tunnel_passes_ascii(two_instance_agw_cmdport):
    """Smoke test: send an ASCII payload through the full chain
    and verify it arrives at App-B."""
    a, b, _, app_b = two_instance_agw_cmdport
    sock = _open_tunnel(a, b, app_b)
    try:
        payload = b"Hello two-instance tunnel"
        sock.sendall(payload)
        received = _drain_app(app_b, expected_min=len(payload), total_timeout=6.0)
    finally:
        sock.close()
    assert b"Hello two-instance tunnel" in received, (
        f"ASCII payload mangled.  Sent {payload!r}, got {received!r}"
    )


# Same byte set as the single-instance #24 test, with CR xfailed
# against the same upstream issue.
_BYTE_CASES = [
    pytest.param(0x00, "NUL", id="0-NUL"),
    pytest.param(0x01, "SOH", id="1-SOH"),
    pytest.param(0x07, "BEL", id="7-BEL"),
    pytest.param(0x08, "BS", id="8-BS"),
    pytest.param(0x09, "TAB", id="9-TAB"),
    pytest.param(0x0A, "LF", id="10-LF"),
    pytest.param(
        0x0D, "CR", id="13-CR",
        marks=pytest.mark.xfail(
            reason="M0LTE/linbpq#24: CR expanded to CR-LF on FBB→CMDPORT path; "
                   "two-instance carries the same CMDPORT relay code",
            strict=True,
        ),
    ),
    pytest.param(0x1A, "Ctrl-Z", id="26-Ctrl-Z"),
    pytest.param(0x1B, "ESC", id="27-ESC"),
    pytest.param(0x7F, "DEL", id="127-DEL"),
    pytest.param(0x80, "high-bit", id="128-high-bit"),
    pytest.param(0xFE, "0xFE", id="254-0xFE"),
    pytest.param(0xFF, "0xFF", id="255-0xFF"),
]


@pytest.mark.parametrize("byte_value,name", _BYTE_CASES)
def test_two_instance_tunnel_byte_transparency(
    two_instance_agw_cmdport, byte_value, name
):
    """Each interesting byte value through the full two-instance
    chain.  Compare against the single-instance variant in
    test_apps_interface_transparency.py — same expected results,
    plus the AX/IP-UDP carrier in the middle."""
    a, b, _, app_b = two_instance_agw_cmdport
    sock = _open_tunnel(a, b, app_b)
    sentinel = bytes([0x41, byte_value, 0x5A])
    try:
        sock.sendall(sentinel)
        received = _drain_app(app_b, expected_min=3, total_timeout=4.0)
    finally:
        sock.close()

    if b"A" not in received or b"Z" not in received[received.index(b"A") + 1:]:
        pytest.fail(
            f"sentinel A<0x{byte_value:02X} {name}>Z not received intact "
            f"through two-instance tunnel.  Got: {received!r}"
        )
    a_idx = received.index(b"A")
    z_idx = received.index(b"Z", a_idx + 1)
    middle = received[a_idx + 1:z_idx]
    assert middle == bytes([byte_value]), (
        f"byte 0x{byte_value:02X} ({name}) mangled in two-instance tunnel.  "
        f"Sent A<0x{byte_value:02X}>Z, received A<{middle!r}>Z"
    )


@pytest.mark.xfail(
    reason="M0LTE/linbpq#24: payload contains 0x0D which is expanded to CR-LF "
           "on the BPQ-B side CMDPORT relay",
    strict=True,
)
def test_two_instance_tunnel_full_byte_sweep(two_instance_agw_cmdport):
    """All 256 byte values in a single record through the chain.

    Carries the AX/IP-UDP layer between the two BPQs on top of
    the same CMDPORT relay that the single-instance test
    exercises — so any byte mangling beyond the known #24
    (CR→CR-LF) would be a new finding in the AX.25 / AXIP layer.
    """
    a, b, _, app_b = two_instance_agw_cmdport
    sock = _open_tunnel(a, b, app_b)
    middle = bytes(range(256))
    payload = b"<<<" + middle + b">>>"
    try:
        sock.sendall(payload)
        received = _drain_app(
            app_b, expected_min=len(payload), total_timeout=10.0
        )
    finally:
        sock.close()

    assert b"<<<" in received and b">>>" in received[received.index(b"<<<"):], (
        f"sentinels missing — chain didn't pass full payload.  "
        f"Got {len(received)} bytes; head: {received[:120]!r}"
    )
    start = received.index(b"<<<") + 3
    end = received.index(b">>>", start)
    got_middle = received[start:end]

    if got_middle == middle:
        return  # Surprise — strict-xfail will flag this as XPASS.

    n = min(len(middle), len(got_middle))
    diffs = [
        (i, middle[i], got_middle[i])
        for i in range(n)
        if middle[i] != got_middle[i]
    ]
    if diffs:
        sample = ", ".join(
            f"idx {i}: sent 0x{s:02X} got 0x{g:02X}" for i, s, g in diffs[:8]
        )
        pytest.fail(
            f"{len(diffs)}/{n} bytes mangled in two-instance sweep.  "
            f"First few: {sample}.  "
            f"Sent {len(middle)} bytes, received {len(got_middle)} bytes."
        )
    pytest.fail(
        f"length mismatch: sent {len(middle)}, got {len(got_middle)}"
    )
