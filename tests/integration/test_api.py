"""JSON API endpoints — coverage for /api/* served on HTTPPORT.

Despite there being a separate ``APIPORT`` config keyword, the API
routes are dispatched via the same HTTP server as the admin pages
(see ``APIProcessHTTPMessage`` called from ``HTTPcode.c``).  These
tests hit the API on the HTTPPORT and assert on the JSON body.

Routes (from ``nodeapi.c::APIList``):

- /api/info, /api/ports, /api/nodes, /api/links, /api/users — open
- /api/mheard, /api/tcpqueues — require a port number param
- /api/v1/config, /api/v1/state — sysop scope
- /api/request_token — issues an auth token
"""

from __future__ import annotations

import json
import socket


def _http_get_json(port: int, path: str, timeout: float = 3.0) -> tuple[bytes, dict | list]:
    """GET ``path`` and return (status_line, parsed JSON body)."""
    with socket.create_connection(("127.0.0.1", port), timeout=timeout) as sock:
        sock.sendall(
            f"GET {path} HTTP/1.0\r\nConnection: close\r\n\r\n".encode("ascii")
        )
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
    head, _, body = data.partition(b"\r\n\r\n")
    status_line = head.split(b"\r\n", 1)[0]
    parsed = json.loads(body.decode("utf-8", errors="replace")) if body else None
    return status_line, parsed


def _http_get_status(port: int, path: str, timeout: float = 3.0) -> bytes:
    """GET ``path`` and return just the status line."""
    with socket.create_connection(("127.0.0.1", port), timeout=timeout) as sock:
        sock.sendall(
            f"GET {path} HTTP/1.0\r\nConnection: close\r\n\r\n".encode("ascii")
        )
        sock.settimeout(timeout)
        head = b""
        while b"\r\n" not in head:
            try:
                chunk = sock.recv(256)
            except (TimeoutError, socket.timeout):
                break
            if not chunk:
                break
            head += chunk
    return head.split(b"\r\n", 1)[0]


def test_api_info_returns_node_identity(linbpq):
    status, body = _http_get_json(linbpq.http_port, "/api/info")
    assert b"200" in status, status
    assert body == {"info": body["info"]}, f"unexpected envelope: {body}"
    info = body["info"]
    assert info["NodeCall"] == "N0CALL"
    assert info["Alias"] == "TEST"
    assert "Version" in info and info["Version"]


def test_api_ports_lists_telnet(linbpq):
    status, body = _http_get_json(linbpq.http_port, "/api/ports")
    assert b"200" in status
    ports = body["ports"]
    assert any(p.get("Driver") == "TELNET" for p in ports), (
        f"no Telnet port in /api/ports: {body!r}"
    )


def test_api_nodes_envelope_present(linbpq):
    """/api/nodes returns an envelope; with an empty NODES table the
    body is currently malformed JSON (``{"nodes":\\n]}`` — see
    https://github.com/M0LTE/linbpq/issues/1).  Lock in the
    recognisable shape rather than valid JSON; once the issue is
    fixed, switch this to a json.loads + ``== {"nodes": []}``."""
    with socket.create_connection(("127.0.0.1", linbpq.http_port), timeout=3) as sock:
        sock.sendall(b"GET /api/nodes HTTP/1.0\r\nConnection: close\r\n\r\n")
        sock.settimeout(3)
        data = b""
        while True:
            try:
                chunk = sock.recv(8192)
            except (TimeoutError, socket.timeout):
                break
            if not chunk:
                break
            data += chunk
    assert b"200 OK" in data, data[:200]
    assert b'"nodes":' in data, f"no 'nodes' envelope: {data[-200:]!r}"


def test_api_users_is_well_formed_when_empty(linbpq):
    status, body = _http_get_json(linbpq.http_port, "/api/users")
    assert b"200" in status
    assert body == {"users": []}, f"expected empty users envelope: {body!r}"


def test_api_v1_state_no_auth_returns_401(linbpq):
    """An HTTP/1.0 GET to ``/api/v1/state`` without an
    ``Authorization: Bearer`` header returns 401.

    Note: this does NOT prove auth is enforced.  The token-verify
    block in ``nodeapi.c::APIProcessHTTPMessage`` is currently
    commented out (see https://github.com/M0LTE/linbpq/issues/5),
    so curl with *any* `Authorization: Bearer` value gets 200.
    The 401 we see here comes from the URL-match catch-all under
    HTTP/1.0; HTTP/1.1 + Auth header reaches the actual handler.
    Once #5 is fixed and real auth lands, expand this into a full
    auth-required suite (no token / bad token / good token / scope).
    """
    status = _http_get_status(linbpq.http_port, "/api/v1/state")
    assert b"401" in status, f"expected 401 without token, got {status!r}"


def test_api_request_token_issues_token(linbpq):
    status, body = _http_get_json(linbpq.http_port, "/api/request_token")
    assert b"200" in status
    token = body.get("access_token")
    assert isinstance(token, str) and len(token) >= 16, (
        f"unexpected token: {body!r}"
    )
    assert "expires_at" in body
    assert body.get("scope") == "create"


def test_api_mheard_without_port_is_rejected(linbpq):
    """/api/mheard requires a port number; absent one, returns 401."""
    status = _http_get_status(linbpq.http_port, "/api/mheard")
    assert b"401" in status, f"expected 401 for /api/mheard, got {status!r}"
