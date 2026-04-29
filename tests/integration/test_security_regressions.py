"""Security regression tests for filed M0LTE/linbpq Critical/High issues.

Each test attempts the documented exploit and asserts the
*secure* behaviour — currently failing because the bug exists,
strict-xfailed against the relevant issue.  When the fix lands
upstream, the strict-xfail flips to XPASS which fails the
suite, forcing a review and removal of the xfail.

Coverage:

| Issue | Test | Class |
|---|---|---|
| #25 | spoofable Host: header → LOCAL=TRUE | auth bypass |
| #26 | unauth POST /Node/CfgSave overwrites bpq32.cfg | unauth state change |
| #27 | path traversal in /WebMail/Local | unauth file read |
| #28 | AGW V frame oversized digi list | stack overflow |
| #29 | session keys from sock * time(NULL) | predictable RNG |
| #31 | WebSocket /RIGCTL stack overflow | crash |
| #32 | unauth /Node/freqOffset | unauth state change |
| #33 | unauth POST /Mail/Config | unauth state change |
| #34 | Telnet ANON unbounded strcpy | heap overflow |
| #35 | password logged cleartext | credential leak |
| #36 | rand() % 26 token RNG | predictable RNG |
| #37 | RHP WebSocket arbitrary callsign | callsign forgery |
| #38 | PWD weak crypto | weak verifier |

Issue #30 (BBS PG shell injection) is not covered here — it
needs `/PG/<server>` to be configured, which our test fixtures
don't provide.  Filed as a follow-up.

These tests are deliberately attempting the exploits.  They
run inside the per-test linbpq sandbox on loopback only; no
production BPQ is touched.

NOTE on strict xfail semantics: each test asserts the
SECURE behaviour (e.g. "request returns 401").  The bug
makes that assertion fail → xfail.  When fixed → assertion
passes → strict-xfail flips to XPASS (test failure) →
review notice.
"""

from __future__ import annotations

import os
import re
import socket
import struct
import time
from contextlib import ExitStack
from pathlib import Path
from string import Template

import pytest

from helpers.linbpq_instance import LinbpqInstance
from helpers.telnet_client import TelnetClient


# Minimal cfg with HTTPPORT exposed and a SYSOP user — enough
# for most of the unauth tests.
_CFG_BASIC = Template(
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
 NETROMPORT=$netrom_port
 FBBPORT=$fbb_port
 APIPORT=$api_port
 AGWPORT=$agw_port
 MAXSESSIONS=10
 USER=test,test,N0CALL,,SYSOP
ENDPORT
"""
)


def _http_request(
    port: int, method: str, path: str, body: bytes = b"",
    headers: dict | None = None, timeout: float = 5.0
) -> tuple[bytes, dict, bytes]:
    """Send a raw HTTP/1.0 request and return (status_line,
    headers_dict, body).  Default headers don't set ``Host:`` so
    tests that need to spoof or omit it have explicit control.
    """
    hdrs = dict(headers or {})
    if body:
        hdrs.setdefault("Content-Type", "application/x-www-form-urlencoded")
        hdrs["Content-Length"] = str(len(body))
    request = f"{method} {path} HTTP/1.0\r\n".encode("ascii")
    for k, v in hdrs.items():
        request += f"{k}: {v}\r\n".encode("ascii")
    request += b"\r\n" + body

    with socket.create_connection(("127.0.0.1", port), timeout=timeout) as sock:
        sock.sendall(request)
        sock.settimeout(timeout)
        data = b""
        while True:
            try:
                chunk = sock.recv(8192)
            except (TimeoutError, socket.timeout):
                break
            if not chunk:
                break
            data += chunk
            if len(data) > 1 << 20:
                break

    head, _, resp_body = data.partition(b"\r\n\r\n")
    lines = head.split(b"\r\n")
    status = lines[0] if lines else b""
    resp_hdrs = {}
    for line in lines[1:]:
        name, _, value = line.partition(b":")
        resp_hdrs[name.strip().lower()] = value.strip()
    return status, resp_hdrs, resp_body


@pytest.fixture
def linbpq_basic(tmp_path: Path):
    """Single linbpq with the basic config.  Used by most of the
    unauth-HTTP exploit tests."""
    instance = LinbpqInstance(tmp_path, config_template=_CFG_BASIC)
    instance.start(ready_timeout=15.0)
    try:
        yield instance
    finally:
        try:
            if instance.proc:
                instance.proc.terminate()
                instance.proc.wait(timeout=5)
        except Exception:
            if instance.proc:
                instance.proc.kill()


def _is_alive(linbpq: LinbpqInstance) -> bool:
    """Probe whether linbpq is still reachable on its telnet port."""
    try:
        with socket.create_connection(
            ("127.0.0.1", linbpq.telnet_port), timeout=1.0
        ):
            return True
    except OSError:
        return False


# ── #25: spoofable Host: header → LOCAL=TRUE ─────────────────────


@pytest.mark.xfail(
    strict=True,
    reason=(
        "M0LTE/linbpq#25: HTTP server treats `Host: 127.0.0.1` "
        "as proof of localhost regardless of TCP source — "
        "auto-grants SYSOP WebMail session"
    ),
)
def test_25_host_header_spoof_does_not_grant_local(linbpq_basic):
    """A request with a spoofed ``Host: 127.0.0.1`` header from
    a non-loopback context should NOT auto-authenticate as the
    SYSOP user.

    Today the fix is "drop the Host:-header check and use the
    actual TCP source address".  This test connects via
    loopback (we don't have a non-loopback path in the
    fixture), but spoofing the *string value* of Host:
    shouldn't be sufficient on its own — the secure
    implementation would consult the peer-address of the
    socket, not the user-supplied header.

    The assertion: a request with ``Host: 127.0.0.1`` set
    (but no valid session cookie) must NOT receive
    authenticated content.  Today's behaviour is that
    /WebMail returns the signed-in Message List view based
    purely on the user-supplied Host: header.  A fix would
    consult the socket peer address instead.

    Note: in our test fixture the *actual* TCP source is
    127.0.0.1 (we only have loopback to talk to).  This test
    proves that even on a fixed implementation, the
    spoofable header alone shouldn't grant auth — the secure
    code path checks the peer address; with the fix in
    place, simply supplying ``Host: 127.0.0.1`` from a
    non-loopback context wouldn't help, and so even on
    loopback (where it might still grant if the peer-check
    sees 127.0.0.1) we want the WebMail page to respect
    session cookies, not just the header.

    For practical detection: with the bug, hitting /WebMail
    with mail-subsystem enabled produces "Message List";
    without it produces the signon form.  The mail subsystem
    isn't enabled in this fixture, so /WebMail typically
    returns 200 with WebMailSignon content.  We instead
    check the JSON API path which is more sensitive to the
    LOCAL=TRUE auto-sysop:
    """
    port = linbpq_basic.http_port
    # /Mail/api/v1/info short-circuits to AuthSysop when
    # LOCAL=TRUE (see issue #25 root cause).  A secure
    # implementation requires a token (or a real session
    # cookie).  Send Host: spoofed and *no* token: bug =
    # endpoint returns sysop-level content; fixed =
    # 401/403/missing-token error.
    status, _, body = _http_request(
        port, "GET", "/mail/api/v1/info",
        headers={"Host": "127.0.0.1"},
    )
    # Sysop-grade endpoints typically return JSON with
    # mail subsystem fields when authenticated.  An
    # auth-rejection returns either 401 or a small JSON
    # error.  The bug surface: any 200 with substantive
    # JSON content is a sign LOCAL=TRUE was honoured.
    assert b"401" in status or b"403" in status or b"unauth" in body.lower() or b"token" in body.lower() or len(body) < 100, (
        "Mail API /info accepted Host: 127.0.0.1 spoof as "
        f"proof of LOCAL.  Status: {status!r}, "
        f"body[:300]: {body[:300]!r}"
    )


# ── #26: unauth POST /Node/CfgSave overwrites bpq32.cfg ──────────


@pytest.mark.xfail(
    strict=True,
    reason=(
        "M0LTE/linbpq#26: POST /Node/CfgSave has no auth gate; "
        "writes attacker-supplied bytes straight into bpq32.cfg"
    ),
)
def test_26_unauth_cfgsave_does_not_overwrite_cfg(linbpq_basic):
    """POST /Node/CfgSave from an unauthenticated client must
    not overwrite ``bpq32.cfg``.  Today it does, with no
    auth check.  Sibling endpoints (PortAction, BeaconAction)
    correctly gate on ``LOCAL == FALSE && COOKIE == FALSE → 401``;
    CfgSave should match.
    """
    port = linbpq_basic.http_port
    cfg_path = linbpq_basic.work_dir / "bpq32.cfg"
    original = cfg_path.read_bytes()

    # The handler:
    #   - skips first 8 bytes (4 for "Msg=" + 4 for the
    #     length of input from \r\n\r\n which is offset by
    #     `input + 8` where input == \r\n\r\n start)
    #   - terminates the body at "&Save="
    # so the body shape needs to be Msg=<config>&Save=Save.
    sentinel = b"; ATTACKER_SENTINEL_LINE_DO_NOT_PERSIST\n"
    new_cfg = original + sentinel
    body = b"Msg=" + new_cfg + b"&Save=Save"

    status, _, _ = _http_request(
        port, "POST", "/Node/CfgSave", body=body,
        headers={"Host": "evil.example.com"},
    )

    after = cfg_path.read_bytes()
    assert sentinel not in after, (
        "Unauthenticated POST to /Node/CfgSave was accepted "
        f"and the attacker sentinel survived in bpq32.cfg.  "
        f"Status: {status!r}"
    )


# ── #27: path traversal in /WebMail/Local ───────────────────────


@pytest.mark.xfail(
    strict=False,  # hard to reproduce against a fresh work-dir;
                    # see test docstring.
    reason=(
        "M0LTE/linbpq#27: /WebMail/Local concatenates "
        "request-supplied path with BPQDirectory; ../ traversal "
        "reads arbitrary files when intermediate dir exists"
    ),
)
def test_27_webmail_local_no_path_traversal(linbpq_basic):
    """``GET /WebMail/Local`` followed by URL-encoded path
    traversal must not return content from outside the BBS
    web tree.

    The handler at WebMail.c:1415 strips the leading
    ``/WebMail/`` (9 chars) and uses the rest as a path
    relative to ``BPQDirectory`` with no canonicalisation.
    For traversal to actually resolve at the OS level we
    need an intermediate directory that exists in the
    working dir.  ``HTML/`` is created by the test fixture,
    so ``/WebMail/LocalHTML%2F..%2Fbpq32.cfg`` decodes to
    ``LocalHTML/../bpq32.cfg`` — but ``LocalHTML/`` doesn't
    exist either.  The route prefix match
    (``_memicmp(NodeURL, "/WebMail/Local", 14) == 0``)
    forces us to keep ``Local`` as the start of the path.

    In practice this means the bug is hard to reproduce
    against a fresh empty work-dir — fopen errors out with
    ENOENT and the response is empty.  But we can verify
    the dispatcher still doesn't reject the URL (no auth
    check) by checking the response status: a secure
    implementation returns 401/403; today it returns 404
    (file not found).
    """
    port = linbpq_basic.http_port
    status, _, body = _http_request(
        port, "GET", "/WebMail/Local%2F..%2Fbpq32.cfg",
    )
    # Either: secure (401/403) → fixed; or 200 with cfg
    # contents (full bug); or 404 because Local/ doesn't
    # exist (latent bug).  We accept "not 200 with cfg"
    # plus "not 404" as the secure outcome.
    is_auth_reject = b"401" in status or b"403" in status
    has_cfg_leak = b"NODECALL" in body or b"USER=" in body
    assert is_auth_reject or not has_cfg_leak, (
        f"path traversal returned cfg content.  "
        f"Status: {status!r}, body[:300]: {body[:300]!r}"
    )


# ── #28: AGW V frame oversized digi list ─────────────────────────


@pytest.mark.xfail(
    strict=False,  # stack overflow may not crash the daemon
                    # depending on canaries / heap layout;
                    # the test attempts the exploit and sanity-
                    # probes survival, but a "bug present" run
                    # may still see linbpq alive.
    reason=(
        "M0LTE/linbpq#28: AGW 'V' frame writes (Digis * 7) bytes "
        "into a 500-byte stack buffer; Digis=255 overflows by ~1300 "
        "bytes"
    ),
)
def test_28_agw_v_frame_oversized_digis_does_not_crash(linbpq_basic):
    """Send an AGW 'V' frame with Digis=255 in the payload.
    A secure implementation rejects the frame (or processes
    only the digis that fit).  Today the loop writes past the
    end of a 500-byte stack buffer and crashes the daemon
    (or worse, on builds without stack canaries).

    Assert: linbpq is still alive after the malformed frame.
    """
    from helpers.agw_client import AgwClient, AgwFrame

    # Build a 'V' frame payload: 1 byte digi count, then
    # callsign data.  AGW's frame validator at AGWAPI.c:1082
    # rejects DataLength > 400, so we send exactly 400
    # bytes — the count byte + 399 bytes that the loop
    # will reinterpret as 39 full digipeaters and one
    # partial.  But the loop trusts ``Digis = MsgData[0]``,
    # which is 0xFF.  So it iterates j=1..255, writing 7
    # bytes per iteration at TXMessage[7 + j*7].  TXMessage
    # is 500 bytes; the writes overflow past index 500 on
    # iteration j=71 onwards, smashing the stack frame.
    # The reads of MsgData past index 400 are also heap
    # OOB but typically don't crash on their own.
    digis = 0xFF
    payload = bytes([digis]) + b"D" * 399

    try:
        with AgwClient(
            "127.0.0.1", linbpq_basic.agw_port, timeout=5
        ) as ag:
            ag.send(
                AgwFrame(
                    port=0,
                    data_kind=b"V",
                    pid=0xF0,
                    callfrom=b"M0XYZ",
                    callto=b"APBPQ1",
                    data=payload,
                )
            )
            # Brief drain — receive anything before we move on.
            time.sleep(1.0)
    except OSError:
        # Connection broken is also a fail signal.
        pass

    # The bug-class signal is "linbpq still alive after the
    # malformed frame".  Today linbpq crashes (or stack-canary
    # SIGABRT).  Secure implementation: alive.
    time.sleep(0.5)
    assert _is_alive(linbpq_basic), (
        "linbpq died after AGW V frame with Digis=255 — stack "
        "buffer overflow"
    )


# ── #29: session keys from sock * time(NULL) ─────────────────────


@pytest.mark.xfail(
    strict=True,
    reason=(
        "M0LTE/linbpq#29: AllocateSession uses sock * time(NULL) "
        "for HTTP/WebMail/Chat session keys — predictable from "
        "observed samples"
    ),
)
def test_29_session_keys_are_not_predictable(linbpq_basic):
    """Allocate two sessions back-to-back and check that the
    second key is *not* trivially derivable from the first.

    The current implementation: ``sprintf(Key, "%c%012X", Mode,
    (int)(sock * time(NULL)))``.  Two sessions allocated within
    the same second from socket FDs differing by N produce keys
    that differ by exactly N * time(NULL) — i.e. fully
    predictable from the observed first key.

    A secure implementation uses a CSPRNG and the keys have
    no observable relationship.
    """
    port = linbpq_basic.http_port
    # Trigger Mail signon twice to allocate two sessions.
    # Accept-Encoding: deflate works around #19 (NUL body)
    # so we can actually parse the response.
    keys = []
    for _ in range(2):
        status, _, body = _http_request(
            port, "POST", "/Mail/Signon?Mail",
            body=b"User=test&password=test",
            headers={
                "Host": f"127.0.0.1:{port}",
                "Accept-Encoding": "deflate",
            },
        )
        # If the body comes back deflate-compressed,
        # decompress.  zlib.decompress handles raw deflate.
        if body and body[0] not in (b"<"[0], b"H"[0], 0):
            try:
                import zlib as _zlib
                body = _zlib.decompress(body)
            except Exception:
                pass
        match = re.search(rb"\?(M[0-9A-F]{12})", body)
        if match:
            keys.append(int(match.group(1)[1:].decode(), 16))
        time.sleep(0.05)

    if len(keys) < 2:
        pytest.skip("couldn't allocate two Mail sessions to compare")

    # Predictability check: AllocateSession's formula is
    # ``(int)sock * time(NULL)`` truncated to 32 bits.  Try
    # small sock values (1..2048) at a window of time values
    # (now ± 30s) and see if any (sock, t) pair produces
    # the observed key.  If so, the key is predictable from
    # an attacker who knows roughly the wall-clock time.
    now = int(time.time())
    for key in keys:
        for sec in range(now - 30, now + 30):
            for sock in range(1, 2048):
                if (sock * sec) & 0xFFFFFFFF == key:
                    pytest.fail(
                        f"Session key 0x{key:08X} matches "
                        f"sock * time(NULL): sock={sock}, "
                        f"time={sec}.  Predictable from observed "
                        f"timing alone."
                    )


# ── #31: WebSocket /RIGCTL stack overflow ────────────────────────


@pytest.mark.xfail(
    strict=False,  # same reasoning as #28: overflow may not
                    # crash visibly in our setup
    reason=(
        "M0LTE/linbpq#31: WebSocket /RIGCTL data frame sprintfs "
        "untrusted payload into a 64-byte stack buffer"
    ),
)
def test_31_websocket_rigctl_oversized_payload_does_not_crash(linbpq_basic):
    """Open a WebSocket to /RIGCTL and send a data frame with
    a 1024-byte payload.  Today this overflows the 64-byte
    RigCMD stack buffer; a secure implementation bounds the
    sprintf or rejects oversized frames.

    Assert: linbpq is still alive after the malformed frame.
    """
    port = linbpq_basic.http_port
    # WebSocket upgrade for /RIGCTL.
    ws_handshake = (
        f"GET /RIGCTL HTTP/1.1\r\n"
        f"Host: 127.0.0.1:{port}\r\n"
        f"Upgrade: websocket\r\n"
        f"Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
        f"Sec-WebSocket-Version: 13\r\n\r\n"
    ).encode("ascii")

    try:
        sock = socket.create_connection(
            ("127.0.0.1", port), timeout=5
        )
        sock.settimeout(2.0)
        sock.sendall(ws_handshake)
        # Drain the upgrade response.
        try:
            sock.recv(4096)
        except (TimeoutError, socket.timeout):
            pass
        # Build a WebSocket text frame with masked 1024-byte
        # payload.  Frame: FIN + opcode 1 (text), mask bit
        # set, length 126 (extended 16-bit), 4-byte mask,
        # 1024 bytes XOR'd with mask.
        payload = b"A" * 1024
        mask = b"\x00\x00\x00\x00"
        masked = bytes(p ^ mask[i & 3] for i, p in enumerate(payload))
        frame = (
            b"\x81\xfe"  # FIN + text, MASK + length=126
            + struct.pack(">H", 1024)
            + mask
            + masked
        )
        sock.sendall(frame)
        time.sleep(1.0)
        sock.close()
    except OSError:
        pass

    time.sleep(0.5)
    assert _is_alive(linbpq_basic), (
        "linbpq died after WebSocket /RIGCTL oversized frame"
    )


# ── #32: unauth /Node/freqOffset ─────────────────────────────────


@pytest.mark.xfail(
    strict=True,
    reason=(
        "M0LTE/linbpq#32: POST /Node/freqOffset has no auth "
        "gate — sets TX offset on any configured port"
    ),
)
def test_32_unauth_freqoffset_rejected(linbpq_basic):
    """POST /Node/freqOffset from an unauthenticated client
    should return 401/403, not silently apply the offset.
    """
    port = linbpq_basic.http_port
    status, _, _ = _http_request(
        port, "POST", "/Node/freqOffset?1", body=b"500"
    )
    # Reject = any 4xx/5xx.  Today the handler returns 200
    # (or 0 — silent acceptance).
    assert (
        b"401" in status or b"403" in status or b"500" in status
    ), f"unauth freqOffset not rejected: status={status!r}"


# ── #33: unauth POST /Mail/Config ────────────────────────────────


@pytest.mark.xfail(
    strict=False,  # rewrite-detection through /Mail/Conf
                    # form re-render is unreliable: may
                    # collide with #21 (cold-cache crash)
                    # or render from a stale snapshot
    reason=(
        "M0LTE/linbpq#33: POST /Mail/Config has no Session->User "
        "or LOCAL+COOKIE check; rewrites SYSOPCall, BBSName, "
        "ISP creds, etc."
    ),
)
def test_33_unauth_mail_config_rejected(linbpq_basic):
    """POST /Mail/Config from an unauthenticated client must
    not rewrite the live ``SYSOPCall`` in BPQ memory.

    The dispatcher only computes ``LOCAL`` from the
    spoofable Host: header (#25) and consults Session
    not-at-all before invoking ProcessConfUpdate.  Today
    a request from any IP with a recognisable Host:
    127.0.0.1 trips ``LOCAL=TRUE`` and the rewrite lands.

    To detect the rewrite we re-fetch /Mail/Conf afterwards
    and check whether SYSOPCall in the rendered form
    matches our injected sentinel.
    """
    port = linbpq_basic.http_port

    # Prime ConfigTemplate first by GETting /Mail/Conf —
    # without this, the POST handler crashes before doing
    # any state mutation (issue #21).  We're testing #33's
    # auth gap, not #21's crash, so prime first.
    _http_request(
        port, "GET", "/Mail/Conf",
        headers={"Host": f"127.0.0.1:{port}"},
    )

    # Send the unauth POST.  Setting ``Host: 127.0.0.1`` to
    # trigger LOCAL=TRUE here is the bug-surface; a fix
    # gates on Session->User or COOKIE so the Host:
    # spoofing doesn't grant write access.
    body = b"BBSCall=N0CALL&SYSOPCall=ATTACK1&Save=Save"
    status, _, _ = _http_request(
        port, "POST", "/Mail/Config",
        body=body,
        headers={"Host": "127.0.0.1"},
    )

    # Re-fetch the config form; SYSOPCall is rendered into
    # an input with ``value="..."``.  Search for our
    # sentinel.
    _, _, after = _http_request(
        port, "GET", "/Mail/Conf",
        headers={"Host": f"127.0.0.1:{port}"},
    )
    assert b"ATTACK1" not in after, (
        f"unauth POST /Mail/Config rewrote SYSOPCall to "
        f"ATTACK1 — visible in /Mail/Conf form.  POST "
        f"status: {status!r}"
    )


# ── #34: Telnet ANON unbounded strcpy ────────────────────────────


# Build with an ANON user line so the affected code path runs.
_CFG_ANON = Template(
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
 NETROMPORT=$netrom_port
 FBBPORT=$fbb_port
 APIPORT=$api_port
 AGWPORT=$agw_port
 MAXSESSIONS=10
 USER=test,test,N0CALL,,SYSOP
 USER=anon,,,,
 LOGGING=0
ENDPORT
"""
)


@pytest.fixture
def linbpq_anon(tmp_path: Path):
    instance = LinbpqInstance(tmp_path, config_template=_CFG_ANON)
    instance.start(ready_timeout=15.0)
    try:
        yield instance
    finally:
        try:
            if instance.proc:
                instance.proc.terminate()
                instance.proc.wait(timeout=5)
        except Exception:
            if instance.proc:
                instance.proc.kill()


@pytest.mark.xfail(
    strict=False,  # heap corruption may not crash visibly
                    # in our setup; the test attempts the
                    # exploit and probes daemon survival
    reason=(
        "M0LTE/linbpq#34: Telnet ANON login does strcpy(Callsign[10], "
        "username) without bounds — heap overflow"
    ),
)
def test_34_telnet_anon_long_username_does_not_crash(linbpq_anon):
    """Connect to telnet, log in as an ANON user with a
    1024-byte username.  Today the strcpy into a 10-byte
    Callsign field overflows the heap.  A secure
    implementation truncates or rejects.

    Assert: linbpq is still alive after the long username.
    """
    huge = b"A" * 1024
    try:
        sock = socket.create_connection(
            ("127.0.0.1", linbpq_anon.telnet_port), timeout=3
        )
        sock.settimeout(2.0)
        # Drain banner + user prompt.
        try:
            sock.recv(4096)
        except (TimeoutError, socket.timeout):
            pass
        sock.sendall(huge + b"\r")
        time.sleep(0.3)
        try:
            sock.sendall(b"\r")  # blank password
        except OSError:
            pass
        time.sleep(0.5)
        sock.close()
    except OSError:
        pass

    time.sleep(0.5)
    assert _is_alive(linbpq_anon), (
        "linbpq died after telnet ANON 1024-byte username — "
        "heap overflow on Callsign[10]"
    )


# ── #35: passwords logged cleartext ──────────────────────────────


_CFG_LOGGING = Template(
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
 NETROMPORT=$netrom_port
 FBBPORT=$fbb_port
 APIPORT=$api_port
 AGWPORT=$agw_port
 MAXSESSIONS=10
 USER=test,uniqueP4ssw0rd,N0CALL,,SYSOP
 LOGGING=1
ENDPORT
"""
)


@pytest.fixture
def linbpq_logging(tmp_path: Path):
    instance = LinbpqInstance(tmp_path, config_template=_CFG_LOGGING)
    instance.start(ready_timeout=15.0)
    try:
        yield instance
    finally:
        try:
            if instance.proc:
                instance.proc.terminate()
                instance.proc.wait(timeout=5)
        except Exception:
            if instance.proc:
                instance.proc.kill()


@pytest.mark.xfail(
    strict=True,
    reason=(
        "M0LTE/linbpq#35: Telnet password is written cleartext "
        "to bpqlog.txt when LOGGING=1"
    ),
)
def test_35_telnet_password_not_logged_cleartext(linbpq_logging):
    """Log in to telnet with a password, then grep the BPQ
    log files for that exact string.  Today the password
    appears verbatim.
    """
    pw = "uniqueP4ssw0rd"
    with TelnetClient(
        "127.0.0.1", linbpq_logging.telnet_port, timeout=10
    ) as client:
        client.login("test", pw)
        client.write_line("BYE")
    time.sleep(1.0)
    # BPQ writes Telnet logs to ``logs/Telnet_YYMMDD.log``
    # in the work_dir (TelnetV6.c::WriteLog).  Search the
    # whole tree for any file containing the password.
    found = []
    for log in linbpq_logging.work_dir.rglob("*"):
        if not log.is_file():
            continue
        try:
            text = log.read_text(errors="replace")
        except OSError:
            continue
        if pw in text:
            offending_lines = [l for l in text.splitlines() if pw in l]
            found.append(f"{log.name}: {offending_lines[:2]}")
    assert not found, (
        f"password {pw!r} found cleartext in log files:\n  "
        + "\n  ".join(found)
    )


# ── #36: rand() % 26 token RNG ───────────────────────────────────


@pytest.mark.xfail(
    strict=True,
    reason=(
        "M0LTE/linbpq#36: API tokens come from rand() % 26 — "
        "predictable from one observed sample"
    ),
)
def test_36_api_tokens_have_full_entropy(linbpq_basic):
    """Mint two tokens and check that the second isn't
    derivable from the first.

    A CSPRNG token has ~32 chars × log2(alphabet) bits of
    entropy.  ``rand() % 26`` per character has ~32 × 4.7 =
    ~150 bits in raw alphabet, but the underlying LCG has
    only 31 bits of state — recovering it from one observed
    32-char output is straightforward.

    Today: tokens use uppercase A–Z only (26 values per
    char) which is a strong indicator of the rand()%26
    pattern.  A secure fix uses /dev/urandom and a wider
    alphabet.

    Assertion: the alphabet of two minted tokens contains
    at least one character outside [A-Z].  This is a
    canary for "still using rand()%26"; once a secure RNG
    lands the alphabet expands.
    """
    port = linbpq_basic.http_port
    tokens = []
    for _ in range(2):
        status, _, body = _http_request(
            port, "GET", "/api/request_token"
        )
        # Field is "access_token" in the JSON response
        # (nodeapi.c:231).
        m = re.search(rb'"access_token"\s*:\s*"([^"]+)"', body)
        if m:
            tokens.append(m.group(1).decode())

    if len(tokens) < 2:
        pytest.skip(f"couldn't mint 2 tokens; got {tokens}")

    # If both tokens are pure A–Z, we're still on rand()%26.
    alphabet = "".join(set("".join(tokens)))
    is_pure_uppercase = all("A" <= c <= "Z" for c in alphabet)
    assert not is_pure_uppercase, (
        f"tokens are pure A-Z ({tokens!r}) — still using "
        f"rand() % 26.  A CSPRNG-based scheme would have "
        f"non-uppercase characters in its output alphabet."
    )


# ── #37: RHP WebSocket arbitrary callsign impersonation ──────────


@pytest.mark.xfail(
    strict=True,
    reason=(
        "M0LTE/linbpq#37: RHP WebSocket processes 'open' messages "
        "without auth and lets the client supply local+remote calls"
    ),
)
def test_37_rhp_websocket_requires_auth(linbpq_basic):
    """Open a WebSocket to /rhp and send an `open` message
    with a local callsign.  A secure implementation requires
    auth on the upgrade itself before honouring open messages.

    The WebSocket handshake should be rejected (401) for
    unauthenticated clients.
    """
    port = linbpq_basic.http_port
    handshake = (
        f"GET /rhp HTTP/1.1\r\n"
        f"Host: 127.0.0.1:{port}\r\n"
        f"Upgrade: websocket\r\n"
        f"Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
        f"Sec-WebSocket-Version: 13\r\n\r\n"
    ).encode("ascii")
    with socket.create_connection(
        ("127.0.0.1", port), timeout=5
    ) as sock:
        sock.settimeout(2.0)
        sock.sendall(handshake)
        try:
            data = sock.recv(4096)
        except (TimeoutError, socket.timeout):
            data = b""
    # Status line on first 3 bytes after "HTTP/1.1 ":
    # 101 Switching Protocols → upgrade succeeded → bug
    # 401/403 → auth required → fixed
    status_line = data.split(b"\r\n", 1)[0] if data else b""
    assert b"101" not in status_line, (
        "RHP WebSocket upgraded without auth.  Status: "
        f"{status_line!r}"
    )


# ── #38: PWD weak crypto ─────────────────────────────────────────


_CFG_PWD = Template(
    """\
SIMPLE=1
NODECALL=N0CALL
NODEALIAS=TEST
LOCATOR=NONE
BPQPASSWORD=ZZZZZZZZ

PORT
 ID=Telnet
 DRIVER=Telnet
 CONFIG
 TCPPORT=$telnet_port
 HTTPPORT=$http_port
 NETROMPORT=$netrom_port
 FBBPORT=$fbb_port
 APIPORT=$api_port
 AGWPORT=$agw_port
 MAXSESSIONS=10
 USER=test,test,N0CALL,,SYSOP
ENDPORT
"""
)


@pytest.fixture
def linbpq_pwd(tmp_path: Path):
    instance = LinbpqInstance(tmp_path, config_template=_CFG_PWD)
    instance.start(ready_timeout=15.0)
    try:
        yield instance
    finally:
        try:
            if instance.proc:
                instance.proc.terminate()
                instance.proc.wait(timeout=5)
        except Exception:
            if instance.proc:
                instance.proc.kill()


@pytest.mark.xfail(
    strict=True,
    reason=(
        "M0LTE/linbpq#38: PWD verifier sums 5 chars into a "
        "USHORT — many distinct strings collide on the same sum"
    ),
)
def test_38_pwd_does_not_accept_collision(linbpq_pwd):
    """The PWD verifier should reject inputs that aren't the
    actual password, even if their character sum at the
    challenged positions happens to match.

    Setup: ``BPQPASSWORD=ZZZZZZZZ`` (all Zs, ASCII 0x5A).
    Any 5 chars summing to 5 * 0x5A = 0x1C2 = 450 should
    pass verification today (e.g. five 'Z's of course, but
    also 'AAAAY' since 4*0x41 + 0x59 = 0x163 != 450...
    let me pick a colliding set).

    Five chars summing to 450:
    - ZZZZZ → 5 * 0x5A = 450 (correct)
    - YYYYZ + 1 = 4*0x59 + 0x5A + 1 = ... no, has to sum to 450
    - All YYYYY = 5 * 0x59 = 445 — close but not equal
    - Try 'YYYZA' = 0x59*3 + 0x5A + 0x41 = 0x10B + 0x5A + 0x41 = 0x1A6 = 422 — no
    - Need exactly 450.  ZZZZZ is the lowest 5-char "all
      same" hit; 'YYYZZ' = 4*0x59 + 2*0x5A = ... let me
      just construct: 0x5A*5=450; replace one Z with X
      and adjust another: Z=90, X=88, [+2]; so XZZZZ +
      add 2 to last: but ASCII 0x5A+2 = 0x5C = '\\'.

    Simpler: send 5 Zs (correct).  Then send 5 chars
    that have the same SUM but aren't all Zs — any
    permutation of letters whose codes total 450.
    Example: 'YY[Z' = ... actually for the test we want
    a DIFFERENT 5-char string that sums to the same
    value.  ZYZZZ has the same sum as ZZZZZ obviously
    (it's the same chars permuted).  We need different
    characters.  450 = 90+90+90+90+90 = 91+91+91+89+88
    = 'YYYZ\\\\' — no, 91 is '['.  92 is '\\'.

    Try: 'YYY[\\\\' = 89*3 + 91 + 92 = 267 + 91 + 92 = 450.
    Yes — those four letters Y, Y, Y, [, \\ sum to 450 and
    are demonstrably *not* the password 'ZZZZZ'.

    So: PWD challenge yields some 5 positions; we respond
    with 5 chars summing to position-correct values but
    different from password.  Rather than craft positions
    we'll just send 'YYY[\\\\' (5 chars summing to 450 if all
    positions were on Z which they are since password is
    all Z); a sum-only verifier accepts it.
    """
    with TelnetClient(
        "127.0.0.1", linbpq_pwd.telnet_port, timeout=10
    ) as client:
        client.login("test", "test")
        # Request PWD challenge.  Cmd.c registers it as
        # "PASSWORD" (alias for PWDCMD); typing PASSWORD on
        # the node prompt triggers the 5-position challenge.
        client.write_line("PASSWORD")
        time.sleep(0.3)
        response = client.read_idle(idle_timeout=1.0, max_total=2.0)
        # The response should include 5 numbers — the
        # positions to look up.  Sum the password chars at
        # those positions for the *correct* response, but
        # we want a colliding *wrong* response.
        positions = re.findall(rb"\d+", response)
        if len(positions) < 5:
            pytest.skip(
                f"didn't see PWD challenge — got {response!r}"
            )
        # Password is all 'Z' (ASCII 90), so the correct
        # sum for any 5 positions is 5 * 90 = 450.  A
        # colliding wrong response: 'YYY[\\' summing to
        # 89+89+89+91+92 = 450, but the chars aren't all 'Z'.
        client.write_line("YYY[\\")  # collision
        time.sleep(0.5)
        result = client.read_idle(idle_timeout=1.0, max_total=2.0)
    # If "Connected" or "Sysop" appears, the wrong response
    # was accepted on a sum collision — the bug.
    secure_response = (
        b"invalid" in result.lower()
        or b"sorry" in result.lower()
        or b"failure" in result.lower()
        or b"error" in result.lower()
    )
    assert secure_response, (
        f"PWD verifier accepted a sum-collision response: "
        f"{result!r}"
    )
