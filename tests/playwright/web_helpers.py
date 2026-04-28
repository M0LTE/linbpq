"""Shared HTTP / signon helpers for the playwright pytest suite.

Every helper sends ``Accept-Encoding: deflate`` and inflates the
response body when the server replies with ``Content-Encoding:
deflate``.  This is required to dodge M0LTE/linbpq#19 — the
no-deflate path on /Mail/ and /WebMail/ sends an uninitialised
buffer.  Real browsers always send the header, so this matches
production traffic exactly.
"""

from __future__ import annotations

import re
import socket
import zlib

_TIMEOUT = 3.0
_MAIL_KEY_RE = re.compile(rb"\?(M[0-9A-F]{12})")
_CHAT_KEY_RE = re.compile(rb"\?(C[0-9A-F]{12})")


def _send_and_recv(request: bytes, port: int, timeout: float) -> bytes:
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
    return data


def _split_response(data: bytes) -> tuple[bytes, dict[bytes, bytes], bytes]:
    head, _, body = data.partition(b"\r\n\r\n")
    lines = head.split(b"\r\n")
    status_line = lines[0] if lines else b""
    headers: dict[bytes, bytes] = {}
    for line in lines[1:]:
        name, _, value = line.partition(b":")
        headers[name.strip().lower()] = value.strip()
    if headers.get(b"content-encoding", b"").lower() == b"deflate":
        body = zlib.decompress(body)
    return status_line, headers, body


def http_get(
    port: int, path: str, timeout: float = _TIMEOUT
) -> tuple[bytes, bytes]:
    """HTTP/1.0 GET on loopback.  Returns (status_line, body).

    Sends ``Host: 127.0.0.1:<port>`` so the server's
    ``strstr(input, "Host: 127.0.0.1")`` LOCAL-detection trips
    (see ``BBSHTMLConfig.c::ProcessMailHTTPMessage``).  Without
    it, /WebMail and parts of /Mail/ refuse to auto-authenticate
    from loopback and serve the signon form instead.
    """
    request = (
        f"GET {path} HTTP/1.0\r\n"
        f"Host: 127.0.0.1:{port}\r\n"
        f"Accept-Encoding: deflate\r\n"
        f"Connection: close\r\n\r\n"
    ).encode("ascii")
    status, _, body = _split_response(_send_and_recv(request, port, timeout))
    return status, body


def http_get_with_headers(
    port: int, path: str, timeout: float = _TIMEOUT
) -> tuple[bytes, dict[bytes, bytes], bytes]:
    """HTTP/1.0 GET that also returns the parsed headers dict."""
    request = (
        f"GET {path} HTTP/1.0\r\n"
        f"Host: 127.0.0.1:{port}\r\n"
        f"Accept-Encoding: deflate\r\n"
        f"Connection: close\r\n\r\n"
    ).encode("ascii")
    return _split_response(_send_and_recv(request, port, timeout))


def http_post(
    port: int,
    path: str,
    body: bytes,
    timeout: float = _TIMEOUT,
    content_type: str = "application/x-www-form-urlencoded",
) -> tuple[bytes, bytes]:
    """HTTP/1.0 POST on loopback.  Returns (status_line, body)."""
    request = (
        f"POST {path} HTTP/1.0\r\n"
        f"Host: 127.0.0.1:{port}\r\n"
        f"Content-Type: {content_type}\r\n"
        f"Content-Length: {len(body)}\r\n"
        f"Accept-Encoding: deflate\r\n"
        f"Connection: close\r\n\r\n"
    ).encode("ascii") + body
    status, _, resp_body = _split_response(
        _send_and_recv(request, port, timeout)
    )
    return status, resp_body


def status_ok(status_line: bytes) -> bool:
    return b"200" in status_line


def mail_signon(port: int) -> str:
    """POST /Mail/Signon?Mail with the SYSOP test creds and return
    the extracted session key (an ``M`` followed by 12 hex chars).

    Raises if the response is missing a session key — typically
    means the BBS isn't fully started yet, or the upstream
    M0LTE/linbpq#18 NULL-Appl bug has come back.
    """
    status, body = http_post(
        port, "/Mail/Signon?Mail", b"User=test&password=test"
    )
    if not status_ok(status):
        raise RuntimeError(
            f"POST /Mail/Signon?Mail returned {status!r}: {body[:200]!r}"
        )
    match = _MAIL_KEY_RE.search(body)
    if not match:
        raise RuntimeError(
            f"no Mail session key in signon response: {body[:200]!r}"
        )
    return match.group(1).decode("ascii")


def chat_signon(port: int) -> str:
    """POST /Chat/Signon?Chat with the SYSOP test creds and return
    the extracted session key (a ``C`` followed by 12 hex chars)."""
    status, body = http_post(
        port, "/Chat/Signon?Chat", b"User=test&password=test"
    )
    if not status_ok(status):
        raise RuntimeError(
            f"POST /Chat/Signon?Chat returned {status!r}: {body[:200]!r}"
        )
    match = _CHAT_KEY_RE.search(body)
    if not match:
        raise RuntimeError(
            f"no Chat session key in signon response: {body[:200]!r}"
        )
    return match.group(1).decode("ascii")


def webmail_signon(port: int, mail_key: str) -> str:
    """POST /WebMail/Signon to enter WebMail UI.  Requires an
    existing Mail session key (call ``mail_signon`` first).
    Returns the WebMail session key (``W`` + 12 hex chars), or
    falls back to the Mail key if the response doesn't carry a
    distinct ``W`` key.
    """
    status, body = http_post(
        port,
        f"/WebMail/Signon?{mail_key}",
        b"User=test&password=test",
    )
    if not status_ok(status):
        raise RuntimeError(
            f"POST /WebMail/Signon returned {status!r}: {body[:200]!r}"
        )
    match = re.search(rb"\?(W[0-9A-F]{12})", body)
    if match:
        return match.group(1).decode("ascii")
    return mail_key


def add_bbs_user(port: int, key: str, callsign: str) -> None:
    """Seed a BBS user via ``POST /Mail/UserSave`` with
    ``Add=<callsign>``.  Requires an active mail session key.
    Idempotent — re-adding an existing call is a no-op server-side.
    """
    status, body = http_post(
        port,
        f"/Mail/UserSave?{key}",
        f"Add={callsign}".encode("ascii"),
    )
    if not status_ok(status):
        raise RuntimeError(
            f"add_bbs_user({callsign}) failed: {status!r}: {body[:200]!r}"
        )


def fetch_user_list(port: int, key: str) -> list[str]:
    """``POST /Mail/UserList.txt`` — returns the BBS user list as
    a list of callsigns.  The endpoint replies with a ``|``-
    separated list followed by an HTML version trailer.
    """
    status, body = http_post(port, f"/Mail/UserList.txt?{key}", b"")
    if not status_ok(status):
        raise RuntimeError(
            f"fetch_user_list failed: {status!r}: {body[:200]!r}"
        )
    # Body looks like: ``CALL1|CALL2|CALL3|...|<!-- Version 1 -->\n</body></html>``
    # Strip the HTML trailer; the remainder is pipe-separated calls.
    text = body.split(b"<!--", 1)[0].rstrip(b"|").decode("ascii", "replace")
    return [c for c in text.split("|") if c]


def send_bbs_message_via_telnet(
    telnet_port: int,
    sender_user: str,
    sender_pass: str,
    *,
    to: str,
    subject: str,
    body_lines: list[str],
    timeout: float = 1.5,
) -> None:
    """Connect to the BBS via telnet, log in, send a message
    using ``S TO:RECIPIENT``, and disconnect cleanly.

    Used by the seeded fixture to populate the BBS message store
    without poking at file formats directly.

    The whole sequence runs with short read timeouts and sleep-
    based pacing; on a normal local boot the full exchange takes
    well under a second.  If the BBS prompts diverge from what we
    expect, the helper still completes — it just doesn't know
    whether the message went through.
    """
    import socket
    import time

    sock = socket.create_connection(("127.0.0.1", telnet_port), timeout=timeout)
    try:
        sock.settimeout(0.3)

        def _drain() -> bytes:
            buf = b""
            try:
                while True:
                    chunk = sock.recv(8192)
                    if not chunk:
                        break
                    buf += chunk
            except (TimeoutError, socket.timeout):
                pass
            return buf

        def _send(line: str) -> None:
            sock.sendall(line.encode("ascii") + b"\r")
            time.sleep(0.1)
            _drain()

        # Login.  Just blast credentials at the prompt — telnet
        # negotiation usually settles after the first read.
        _drain()
        _send(sender_user)
        _send(sender_pass)
        _drain()
        # Switch to BBS app — first prompt asks for a name (single
        # word).  Any single-word name works; "Test" is fine.
        _send("BBS")
        _send("Test")
        # Send-message sequence: S <recipient> → "Enter Title:" →
        # title → "Enter Message Text..." → body → /EX terminator.
        _send(f"S {to}")
        _send(subject)
        for line in body_lines:
            _send(line)
        _send("/EX")
        _send("B")  # Bye
    finally:
        try:
            sock.close()
        except OSError:
            pass
