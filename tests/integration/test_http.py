"""Phase 2 — HTTP admin: page content, not just a 200."""

from __future__ import annotations

import socket


def _http_get(port: int, path: str, timeout: float = 3.0) -> tuple[bytes, bytes]:
    """Tiny HTTP/1.0 GET on loopback. Returns (status_line, body)."""
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
    return status_line, body


def test_http_root_redirects_to_node_index(linbpq):
    """GET / serves a meta-refresh to /Node/NodeIndex.html."""
    status, body = _http_get(linbpq.http_port, "/")
    assert b"200" in status, f"unexpected status: {status!r}"
    assert b"NodeIndex.html" in body, (
        f"root did not redirect to NodeIndex: {body[:200]!r}"
    )


def test_http_node_index_renders(linbpq):
    """The Node index page contains the configured node call sign."""
    status, body = _http_get(linbpq.http_port, "/Node/NodeIndex.html")
    assert b"200" in status, f"unexpected status: {status!r}"
    assert b"N0CALL" in body, (
        f"node call not on NodeIndex.html: {body[:400]!r}"
    )
