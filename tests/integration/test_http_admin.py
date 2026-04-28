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


# Pages reachable from the standard nav bar — each ships the
# common "BPQ32 Node N0CALL" wrapper plus the menu links.
ADMIN_PAGES_WITH_NAV = [
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
    "/Node/MailMgmt.html",
]


# Other pages served by the admin HTTP server; these don't carry the
# common nav-bar wrapper but should still 200 and not be empty.
# /Node/Streams is the popup-window stream-status page with its own
# minimal HTML; /Node/EditCfg.html is the config-editor textarea.
#
# /WebMail is intentionally NOT listed here: with the mail subsystem
# disabled it returns 641 NUL bytes (uninitialised buffer) — see
# https://github.com/M0LTE/linbpq/issues/2.  Add it back once that's
# fixed, gated on the linbpq_mail fixture.
ADMIN_PAGES_BARE = [
    "/Node/Streams",
    "/Node/EditCfg.html",
]


@pytest.mark.parametrize("path", ADMIN_PAGES_WITH_NAV)
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


@pytest.mark.parametrize("path", ADMIN_PAGES_BARE)
def test_admin_bare_page_renders(linbpq, path):
    """Non-nav pages just need to 200 with non-empty HTML."""
    status, body = _http_get(linbpq.http_port, path)
    assert b"200" in status, f"{path}: unexpected status {status!r}"
    assert len(body) > 0, f"{path}: empty body"
    assert b"<" in body, f"{path}: not HTML: {body[:80]!r}"


def test_unknown_static_asset_404s(linbpq):
    """Requests for files that genuinely don't exist return 404."""
    status, _ = _http_get(linbpq.http_port, "/no-such-file.html")
    assert b"404" in status, f"expected 404 for /no-such-file.html, got {status!r}"


def test_favicon_served(linbpq):
    """favicon.ico is bundled from NodePages.zip and served as an image."""
    status, body = _http_get(linbpq.http_port, "/favicon.ico")
    assert b"200" in status, f"expected 200 for /favicon.ico, got {status!r}"
    assert len(body) > 0, "favicon.ico body empty"


def test_background_served(linbpq):
    """background.jpg is bundled from NodePages.zip and referenced by many templates."""
    status, body = _http_get(linbpq.http_port, "/background.jpg")
    assert b"200" in status, f"expected 200 for /background.jpg, got {status!r}"
    assert len(body) > 0, "background.jpg body empty"
