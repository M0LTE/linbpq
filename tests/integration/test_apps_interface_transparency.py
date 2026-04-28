"""Binary-transparency tests for the LinBPQ Apps Interface.

The apps-interface tunnel — telnet user → BPQ → ``CMDPORT`` app —
is the path that an external application uses to ride a BPQ
session.  For an app-to-app tunnel over RF (two BPQs connected
over an AX.25 link), every byte sent at one end must arrive
unchanged at the other; otherwise binary protocols break.

These tests pin transparency at two layers:

1. **Single-instance**: telnet user → BPQ → CMDPORT app.  Tests
   each "interesting" byte value and a full 256-byte sweep.  This
   is the inner layer — if it fails, two-instance can't pass.

2. **Two-instance**: telnet user → BPQ-A → AX/IP-UDP → BPQ-B →
   CMDPORT app on B.  This is the actual deployment shape.

We *file* findings as M0LTE/linbpq issues per project policy
("we're just outputting issues at this point, not fixing them").
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
from helpers.telnet_client import TelnetClient


# ── Single-instance harness ──────────────────────────────────────


_SINGLE_CFG = Template(
    """\
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
 FBBPORT=$fbb_port
 MAXSESSIONS=10
 USER=test,test,N0CALL,,SYSOP
 CMDPORT $cmd_app_port
ENDPORT
"""
)


def _single_template(cmd_app_port: int) -> Template:
    base = _SINGLE_CFG.template

    class _T(Template):
        def substitute(self, **kw):
            return Template.substitute(self, cmd_app_port=cmd_app_port, **kw)

    return _T(base)


@contextmanager
def _cmdport_app_ctx():
    app = CmdportApp()
    try:
        yield app
    finally:
        app.close()


@contextmanager
def _started(linbpq: LinbpqInstance):
    linbpq.start(ready_timeout=15.0)
    try:
        yield linbpq
    finally:
        try:
            if linbpq.proc:
                linbpq.proc.terminate()
                linbpq.proc.wait(timeout=5)
        except Exception:
            if linbpq.proc:
                linbpq.proc.kill()


@pytest.fixture
def single_instance_with_app(tmp_path: Path):
    """One linbpq + one fake CMDPORT app.  Yields ``(linbpq, app)``."""
    with ExitStack() as stack:
        app = stack.enter_context(_cmdport_app_ctx())
        linbpq = LinbpqInstance(
            tmp_path,
            config_template=_single_template(app.port),
        )
        stack.enter_context(_started(linbpq))
        yield linbpq, app


def _dial_cmdport_via_telnet(linbpq: LinbpqInstance, app: CmdportApp) -> TelnetClient:
    """Open a telnet client, log in, dial CMDPORT[0], confirm app
    received the inbound TCP connection.  Returns the open
    TelnetClient ready for further raw writes.

    NOTE: telnet is NOT 8-bit clean per RFC 854 — CR/LF are
    normalised, BS / BEL / SO / DEL are filtered, and 0xFF starts
    an IAC command sequence.  The transparency tests here use
    FBB host mode for the user side (which IS 8-bit clean) and
    keep this telnet helper around only for sanity checks.
    """
    client = TelnetClient("127.0.0.1", linbpq.telnet_port, timeout=10)
    client.login("test", "test")
    client.write_line("C 1 HOST 0")
    client.read_idle(idle_timeout=1.0, max_total=4.0)
    assert app.wait_for_client(timeout=4.0), (
        "CMDPORT app never received inbound dial"
    )
    intro = app.recv(timeout=1.5)
    assert b"N0CALL" in intro, (
        f"expected calling-station intro from BPQ, got {intro!r}"
    )
    return client


def _dial_cmdport_via_fbb(
    linbpq: LinbpqInstance, app: CmdportApp
) -> socket.socket:
    """8-bit-clean alternative to ``_dial_cmdport_via_telnet``.

    FBB host mode (``FBBPORT``) doesn't do telnet IAC negotiation
    or CR/LF normalisation, so it's the correct path for binary
    tunnel tests.  Returns the raw socket already past login +
    CMDPORT dial; subsequent ``send`` / ``recv`` is byte-clean.
    """
    sock = socket.create_connection(
        ("127.0.0.1", linbpq.fbb_port), timeout=10
    )
    sock.settimeout(2.0)
    sock.sendall(b"test\r")
    time.sleep(0.2)
    sock.sendall(b"test\r")
    time.sleep(0.4)
    # Drain login output.
    try:
        while True:
            data = sock.recv(4096)
            if not data:
                break
            if b"TEST:N0CALL}" in data:
                break
    except (socket.timeout, TimeoutError):
        pass
    sock.sendall(b"C 1 HOST 0\r")
    time.sleep(1.0)
    # Drain dial response.
    try:
        sock.settimeout(1.0)
        while True:
            data = sock.recv(4096)
            if not data:
                break
            if b"Connected to" in data or b"APPL" in data:
                break
    except (socket.timeout, TimeoutError):
        pass
    assert app.wait_for_client(timeout=4.0), (
        "CMDPORT app never received inbound dial via FBB"
    )
    intro = app.recv(timeout=1.5)
    assert b"N0CALL" in intro, (
        f"expected calling-station intro from BPQ, got {intro!r}"
    )
    return sock


def _drain_app_until_idle(
    app: CmdportApp, expected_min: int, total_timeout: float = 8.0
) -> bytes:
    """Read from ``app`` until ``expected_min`` bytes have arrived
    or ``total_timeout`` elapses.  Returns whatever was collected.

    Generous timeouts because the chain is many hops and BPQ may
    buffer at any layer.
    """
    buf = b""
    deadline = time.monotonic() + total_timeout
    last_grew = time.monotonic()
    while time.monotonic() < deadline:
        if len(buf) >= expected_min:
            # Got enough; do one extra short drain in case more is
            # in flight, then return.
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
            # 1.5s of total silence after seeing some data — done.
            break
    return buf


# ── Single-instance: each "interesting" byte ─────────────────────


# ── Telnet → CMDPORT: documented as NOT 8-bit clean ──────────────


def test_telnet_to_cmdport_not_8bit_clean(single_instance_with_app):
    """Document that the *telnet* path mangles bytes en route to
    a CMDPORT app.

    Sending ``\\x00..\\xff`` through ``TCPPORT`` → BPQ → CMDPORT
    produces a result with at least these mutations:

    - 0x07 (BEL), 0x08 (BS), 0x0E (SO), 0xFF (IAC) dropped.
    - 0x0A (LF) repositioned to follow 0x0D (CR-LF normalisation).

    This is by-design telnet behaviour (RFC 854).  Any binary
    tunnel use-case must use the FBB host-mode listener
    (``FBBPORT``) — see ``test_fbb_to_cmdport_*`` below.
    """
    linbpq, app = single_instance_with_app
    middle = bytes(range(256))
    payload = b"<<<" + middle + b">>>"
    with _dial_cmdport_via_telnet(linbpq, app) as client:
        client.write_raw(payload)
        received = _drain_app_until_idle(
            app, expected_min=len(payload), total_timeout=6.0
        )
    # The very fact that it ISN'T equal proves the test's premise.
    # If a future change made telnet 8-bit clean, flip this test.
    assert middle != received[received.index(b"<<<") + 3:received.rfind(b">")], (
        "telnet path is unexpectedly 8-bit clean — update this "
        "test (and consider whether the change is intentional)."
    )


# ── FBB → CMDPORT: must be 8-bit clean ───────────────────────────


# The FBB → CMDPORT path: documented findings.
# - 12 of the 13 interesting byte values round-trip cleanly.
# - 0x0D (CR) is expanded to ``\r\n`` (M0LTE/linbpq#24).  We
#   xfail that case rather than skip so the test will start
#   passing automatically when the upstream code is fixed.

_FBB_BYTE_CASES = [
    pytest.param(0x00, "NUL", id="0-NUL"),
    pytest.param(0x01, "SOH", id="1-SOH"),
    pytest.param(0x07, "BEL", id="7-BEL"),
    pytest.param(0x08, "BS", id="8-BS"),
    pytest.param(0x09, "TAB", id="9-TAB"),
    pytest.param(0x0A, "LF", id="10-LF"),
    pytest.param(
        0x0D,
        "CR",
        id="13-CR",
        marks=pytest.mark.xfail(
            reason="M0LTE/linbpq#24: CR expanded to CR-LF on FBB→CMDPORT path",
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


@pytest.mark.parametrize("byte_value,name", _FBB_BYTE_CASES)
def test_fbb_to_cmdport_byte_transparency(
    single_instance_with_app, byte_value, name
):
    """FBB host mode → BPQ → CMDPORT[0] app, individual byte
    transparency.  Sends ``A<byte>Z`` so the byte is locatable
    in the receiver buffer regardless of any leading/trailing
    junk.

    FBB is the BPQ host-mode listener — 8-bit clean by design:
    no IAC negotiation, no CR/LF normalisation.  If a byte fails
    to round-trip through this path, it's a real BPQ binary-
    transparency bug.

    Currently 12/13 pass; CR is xfailed against issue #24.
    """
    linbpq, app = single_instance_with_app
    sentinel = bytes([0x41, byte_value, 0x5A])

    sock = _dial_cmdport_via_fbb(linbpq, app)
    try:
        sock.sendall(sentinel)
        received = _drain_app_until_idle(
            app, expected_min=3, total_timeout=4.0
        )
    finally:
        sock.close()

    if b"A" not in received or b"Z" not in received[received.index(b"A") + 1:]:
        pytest.fail(
            f"sentinel A<0x{byte_value:02X} {name}>Z not received intact "
            f"via FBB.  Got: {received!r}"
        )
    a_idx = received.index(b"A")
    z_idx = received.index(b"Z", a_idx + 1)
    middle = received[a_idx + 1:z_idx]
    assert middle == bytes([byte_value]), (
        f"byte 0x{byte_value:02X} ({name}) mangled via FBB.  "
        f"Sent A<0x{byte_value:02X}>Z, received A<{middle!r}>Z"
    )


@pytest.mark.xfail(
    reason="M0LTE/linbpq#24: payload contains 0x0D which is expanded to CR-LF",
    strict=True,
)
def test_fbb_to_cmdport_full_byte_sweep(single_instance_with_app):
    """All 256 byte values 0x00..0xFF in a single payload via FBB.
    Length, ordering, and content all have to match.

    xfailed because the payload includes 0x0D, hit by issue #24.
    Once #24 is fixed this test should start passing without
    further changes."""
    linbpq, app = single_instance_with_app
    middle = bytes(range(256))
    payload = b"<<<" + middle + b">>>"

    sock = _dial_cmdport_via_fbb(linbpq, app)
    try:
        sock.sendall(payload)
        received = _drain_app_until_idle(
            app, expected_min=len(payload), total_timeout=8.0
        )
    finally:
        sock.close()

    if b"<<<" not in received:
        pytest.fail(f"start sentinel not seen.  Got {received[:120]!r}")
    if b">>>" not in received[received.index(b"<<<"):]:
        pytest.fail(
            f"end sentinel not seen.  Got {len(received)} bytes; "
            f"head: {received[:160]!r}"
        )

    start = received.index(b"<<<") + 3
    end = received.index(b">>>", start)
    got_middle = received[start:end]

    if got_middle == middle:
        return

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
            f"{len(diffs)}/{n} bytes mangled via FBB.  First few: "
            f"{sample}.  Sent {len(middle)} bytes, received "
            f"{len(got_middle)} bytes."
        )
    pytest.fail(
        f"FBB length mismatch: sent {len(middle)}, received "
        f"{len(got_middle)}"
    )


@pytest.mark.xfail(
    reason=(
        "M0LTE/linbpq#24: counter value 13 includes 0x0D byte expanded "
        "to CR-LF, breaking length and offsets"
    ),
    strict=False,  # may pass intermittently if buffering hides the issue
)
def test_fbb_to_cmdport_burst_ordering(single_instance_with_app):
    """1024 bytes (256 four-byte big-endian counters) through FBB
    must arrive in order without duplication or loss.

    Counter value 13 packs as ``\\x00\\x00\\x00\\x0D`` — that
    0x0D triggers issue #24's CR-LF expansion, throwing every
    subsequent counter offset off by one byte.  xfail until #24
    fixed."""
    import struct

    linbpq, app = single_instance_with_app
    chunks = [struct.pack(">I", i) for i in range(256)]
    payload = b"<<<" + b"".join(chunks) + b">>>"

    sock = _dial_cmdport_via_fbb(linbpq, app)
    try:
        sock.sendall(payload)
        received = _drain_app_until_idle(
            app, expected_min=len(payload), total_timeout=8.0
        )
    finally:
        sock.close()

    assert b"<<<" in received and b">>>" in received[received.index(b"<<<"):], (
        f"sentinels missing in {len(received)} byte response.  "
        f"Head: {received[:120]!r}"
    )
    start = received.index(b"<<<") + 3
    end = received.index(b">>>", start)
    body = received[start:end]
    assert len(body) == 256 * 4, (
        f"length wrong: sent {256 * 4}, got {len(body)}"
    )
    for i in range(256):
        chunk = body[i * 4:(i + 1) * 4]
        (got,) = struct.unpack(">I", chunk)
        assert got == i, (
            f"counter at offset {i * 4}: expected {i}, got {got}"
        )
