"""Static asset serving + URL routing edge cases.

Locks in the contracts that aren't tied to a specific template:
content-type detection by file extension, the ``/`` → index.html
fallback, the bundled NodePages assets, and 404 for genuinely
unknown paths.
"""

from __future__ import annotations

from web_helpers import http_get, http_get_with_headers


def test_root_serves_index_or_inline(linbpq_web):
    """``/`` should 200 with HTML.  If ``HTML/index.html`` is on
    disk it's served verbatim (overrides the inline ``Index``
    template); otherwise the inline template is used.  We don't
    care which path runs, only that it returns a real HTML page.
    """
    port = linbpq_web["http_port"]
    status, body = http_get(port, "/")
    assert b"200" in status, f"GET /: {status!r}"
    assert b"<html" in body.lower() or b"<!doctype" in body.lower()


def test_index_html_404s_or_serves(linbpq_web):
    """Either ``/Index.html`` serves the same page as ``/`` (when
    HTML/index.html exists on disk) or a 404.  Both are valid —
    pin that the response is a real HTTP reply, never 912 NULs
    or similar uninitialised garbage."""
    port = linbpq_web["http_port"]
    status, body = http_get(port, "/Index.html")
    assert b"HTTP/1.1" in status
    # No matter the status, body should be small text/HTML
    if b"200" in status:
        assert b"<" in body[:50]
    else:
        # 404 page is short; body is an error stub
        assert len(body) < 4096


def test_favicon_served_as_image(linbpq_web):
    """favicon.ico (bundled from NodePages.zip) returns 200 with
    Content-Type starting with ``image``."""
    port = linbpq_web["http_port"]
    status, headers, body = http_get_with_headers(port, "/favicon.ico")
    assert b"200" in status
    assert headers.get(b"content-type", b"").lower().startswith(b"image"), (
        f"favicon.ico content-type wrong: {headers!r}"
    )
    # ICO files start with 0x00 0x00 0x01 0x00 (icon resource).
    assert len(body) > 0


def test_background_served_as_image(linbpq_web):
    """background.jpg (bundled) returns 200 with image content-type."""
    port = linbpq_web["http_port"]
    status, headers, body = http_get_with_headers(port, "/background.jpg")
    assert b"200" in status
    assert headers.get(b"content-type", b"").lower().startswith(b"image"), (
        f"background.jpg content-type wrong: {headers!r}"
    )
    # JPEG magic = FF D8 FF.
    assert body[:3] == b"\xff\xd8\xff", (
        f"background.jpg not a JPEG: first bytes {body[:8]!r}"
    )


def test_unknown_path_404(linbpq_web):
    """A path that doesn't match any route returns 404."""
    port = linbpq_web["http_port"]
    status, _ = http_get(port, "/no-such-file.html")
    assert b"404" in status, f"expected 404, got {status!r}"


def test_samples_subdir_reachable(linbpq_web):
    """Files under HTML/samples/ are reachable directly.  Locks in
    that ``SendMessageFile`` walks subdirs of HTML/."""
    port = linbpq_web["http_port"]
    status, body = http_get(port, "/samples/index.html")
    assert b"200" in status
    assert b"<html" in body.lower()


def test_webproc_css_serves_css_content(linbpq_web):
    """``/Node/webproc.css`` is the admin-page stylesheet.  The
    server inlines the CSS on this URL but currently mis-labels
    it as ``text/html`` — browsers fall back to sniffing CSS
    selectors and apply it anyway, so it works in practice.

    Lock in: 200, non-empty body containing CSS-style declarations.
    Don't pin the content-type; that's a known upstream quirk and
    fixing it isn't in scope here.
    """
    port = linbpq_web["http_port"]
    status, _, body = http_get_with_headers(port, "/Node/webproc.css")
    assert b"200" in status, f"GET /Node/webproc.css: {status!r}"
    assert len(body) > 50, "webproc.css suspiciously small"
    assert b".dropdown" in body or b".btn" in body, (
        f"body doesn't look like CSS: {body[:200]!r}"
    )


def test_webmail_webscript_js_served_as_javascript(linbpq_web):
    """``/WebMail/webscript.js`` is the WebMail UI's JS helper.
    The HTML/ file is webscript.js — the route maps it under
    /WebMail/.  Must come back as javascript content-type."""
    port = linbpq_web["http_port"]
    # Try the WebMail-prefixed path first; some builds also serve
    # at /webscript.js.
    for path in ("/WebMail/webscript.js", "/webscript.js"):
        status, headers, body = http_get_with_headers(port, path)
        if b"200" in status:
            ctype = headers.get(b"content-type", b"").lower()
            assert b"javascript" in ctype, (
                f"{path} content-type wrong: {ctype!r}"
            )
            assert len(body) > 100, f"{path} suspiciously small"
            return
    raise AssertionError("webscript.js not served at any tried path")
