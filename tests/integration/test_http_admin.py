"""HTTP admin pages — coverage canaries.

Each linked page in the BPQ32 web admin UI shares a common header
(``BPQ32 Node N0CALL``) and a top navigation bar.  These tests fetch
every standard page and assert that:

- The status line is HTTP 200.
- The page renders with the BPQ32 wrapper, not a "not found" stub.
- The navigation links are present (so a regression in the menu
  builder lands red).

This is breadth-first: it doesn't validate the page-specific content
beyond the wrapper, which is the right level for a regression canary
across many pages.
"""

from __future__ import annotations

import socket

import pytest


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


# Pages discovered in the linbpq web admin.  Each is reachable from
# the navigation menu of any other admin page.
ADMIN_PAGES = [
    "/Node/NodeIndex.html",
    "/Node/Status.html",
    "/Node/About.html",
    "/Node/PortInfo.html",
    "/Node/Routes.html",
    "/Node/Nodes.html",
    "/Node/Ports.html",
    "/Node/Links.html",
    "/Node/Users.html",
    "/Node/Stats.html",
    "/Node/MH.html",
]


@pytest.mark.parametrize("path", ADMIN_PAGES)
def test_admin_page_renders(linbpq, path):
    status, body = _http_get(linbpq.http_port, path)
    assert b"200" in status, f"{path}: unexpected status {status!r}"
    assert b"BPQ32 Node N0CALL" in body, (
        f"{path}: page wrapper missing; body[:200]: {body[:200]!r}"
    )
    # The standard nav bar links every page back to the others.
    assert b"/Node/Routes.html" in body, (
        f"{path}: nav menu missing 'Routes' link"
    )
    assert b"/Node/Nodes.html" in body, (
        f"{path}: nav menu missing 'Nodes' link"
    )


def test_unknown_static_asset_404s(linbpq):
    """Requests for files that genuinely don't exist return 404."""
    status, _ = _http_get(linbpq.http_port, "/favicon.ico")
    assert b"404" in status, f"expected 404 for /favicon.ico, got {status!r}"
