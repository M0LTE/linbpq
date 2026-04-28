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
    """HTTP/1.0 GET on loopback.  Returns (status_line, body)."""
    request = (
        f"GET {path} HTTP/1.0\r\n"
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
