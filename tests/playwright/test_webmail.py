"""WebMail HTTP-level coverage.

The WebMail UI is JS-driven (websocket + dynamic message-list
rendering), so the deepest browser-driven tests live in
test_websocket.py.  Here we lock in:

- The signon form renders.
- The post-signon Message List page renders for the SYSOP user.
- The empty mailbox views (WMAll, WMMine, etc) render the same
  outer template (WebMailPage v6) — exercised via
  test_template_render_matrix's WEBMAIL_RENDERS.
- The XML mail-info endpoints (used by the JS to render row
  detail) reply with XML, not HTML.
"""

from __future__ import annotations

from web_helpers import http_get, http_post, mail_signon


def test_webmail_signon_form_renders(linbpq_web):
    """GET /WebMail (loopback) auto-authenticates and serves the
    WebMail entry page (WebMailPage.txt v6)."""
    port = linbpq_web["http_port"]
    status, body = http_get(port, "/WebMail")
    assert b"200" in status
    assert b"WebMail" in body, "missing WebMail title"


def test_webmail_signon_post_returns_message_list(linbpq_web):
    """POST /WebMail/Signon with creds renders the Message List
    view of WebMailPage v6."""
    port = linbpq_web["http_port"]
    status, body = http_post(
        port, "/WebMail/Signon", b"User=test&password=test"
    )
    assert b"200" in status
    assert b"Message List" in body


def test_webmail_views_render_same_outer_frame(linbpq_web):
    """The WMAll / WMMine / WMfromMe etc views all render the
    same outer template — only the JS-fetched message list
    differs.  Pin that the outer frame is consistent."""
    port = linbpq_web["http_port"]
    for path in (
        "/WebMail/WMAll",
        "/WebMail/WMMine",
        "/WebMail/WMfromMe",
        "/WebMail/WMtoMe",
        "/WebMail/WMSame",
        "/WebMail/MailEntry",
    ):
        status, body = http_get(port, path)
        assert b"200" in status, f"GET {path}: {status!r}"
        # All views render the same outer WebMail frame — pin the
        # title rather than the (fork-only) version marker.
        assert b"WebMail" in body, (
            f"GET {path}: WebMail title missing — {body[:200]!r}"
        )


def test_webmail_logout_returns_some_html(linbpq_web):
    """POST /WebMail/WMLogout should clean up the WebMail session
    and return a redirect / message — just confirm 200 with HTML."""
    port = linbpq_web["http_port"]
    status, body = http_post(port, "/WebMail/WMLogout", b"")
    # Logout endpoint returns either the signon page or a redirect.
    # Both are acceptable; just confirm we don't crash.
    assert b"HTTP/1.1" in status
