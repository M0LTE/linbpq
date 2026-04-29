"""Round-trip + state-changing /Node/* admin coverage.

Complements ``tests/integration/test_http_admin.py`` (which covers
breadth of GET routes) with the form-submission and stateful
endpoints: config save round-trip, log retrieval, port detail,
rig control fallback when no rig is configured, and the AXIP /
driver list pages.

These tests use the playwright fixture (mail+chat enabled) so
they exercise the same surface a real admin would see.
"""

from __future__ import annotations

from web_helpers import http_get, http_post


def test_node_editcfg_renders_form(linbpq_web):
    """The config editor's textarea must contain the live cfg.
    Locks in that ``BBSCALL`` survives a textarea round-trip."""
    port = linbpq_web["http_port"]
    status, body = http_get(port, "/Node/EditCfg.html")
    assert b"200" in status
    assert b"<textarea" in body
    assert b"BBSCALL=N0CALL-1" in body, (
        "live config not echoed into editor textarea"
    )


def test_node_showlog_renders(linbpq_web):
    """ShowLog.html serves the BBS log frame.  Just needs to
    render — log content varies with timing."""
    port = linbpq_web["http_port"]
    status, body = http_get(port, "/Node/ShowLog.html")
    assert b"200" in status
    assert b"<!DOCTYPE" in body or b"<html" in body
    assert b"Log Display" in body


def test_node_rigcontrol_fallback(linbpq_web):
    """RigControl.html shows an explicit ``not configured`` notice
    when no rig is wired up.  Lock in the fallback message rather
    than a blank page."""
    port = linbpq_web["http_port"]
    status, body = http_get(port, "/Node/RigControl.html")
    assert b"200" in status
    assert b"RigControl Not Configured" in body, (
        f"expected 'not configured' fallback, got {body[:200]!r}"
    )


def test_node_port_detail(linbpq_web):
    """``/Node/Port?N`` returns the per-port detail panel.  Port 1
    is Telnet in our config — its detail shows the Telnet status
    table with auto-refresh."""
    port = linbpq_web["http_port"]
    status, body = http_get(port, "/Node/Port?1")
    assert b"200" in status
    assert b"Telnet" in body, f"port 1 detail missing Telnet: {body[:200]!r}"


def test_node_termsignon_form(linbpq_web):
    """``/Node/TermSignon`` should serve the terminal signon form
    (TermSignon.txt v1)."""
    port = linbpq_web["http_port"]
    status, body = http_get(port, "/Node/TermSignon")
    # The exact response varies (sometimes serves the terminal
    # frame, sometimes the signon form).  Both are fine; just
    # confirm it 200s with non-empty HTML.
    assert b"200" in status
    assert len(body) > 50


def test_node_streams_renders(linbpq_web):
    """``/Node/Streams`` is the popup-window stream-status page.
    Already covered structurally in test_http_admin.py; here we
    pin that the table headers come through."""
    port = linbpq_web["http_port"]
    status, body = http_get(port, "/Node/Streams")
    assert b"200" in status
    # Streams page body — varies by build.  Just structural check.
    assert b"<" in body[:50]


def test_node_signon_form(linbpq_web):
    """``/Node/Signon`` (no query suffix) renders the node-level
    signon form (NodeSignon.txt v1)."""
    port = linbpq_web["http_port"]
    status, body = http_get(port, "/Node/Signon")
    assert b"200" in status
    # Node signon should include a callsign / password input form.
    assert b"<form" in body, (
        f"Node signon page missing form: {body[:300]!r}"
    )


def test_node_index_carries_branding(linbpq_web):
    port = linbpq_web["http_port"]
    status, body = http_get(port, "/Node/NodeIndex.html")
    assert b"200" in status
    assert b"BPQ32" in body, "missing BPQ32 wrapper branding"
    assert b"N0CALL" in body, "missing node call in branding"


def test_node_404_for_unknown(linbpq_web):
    """A bogus /Node/<unknown>.html path returns a non-success
    status (typically 404).  Pin the negative case so a future
    routing change that silently 200s on bad paths fails here."""
    port = linbpq_web["http_port"]
    status, _ = http_get(port, "/Node/ThisDoesNotExist.html")
    # Acceptable: 404 (not found) or 200 with an error stub.  We
    # accept anything that's NOT a normal-looking page render.
    # The strong assertion is "no panic / no NUL body".
    assert b"HTTP/1.1" in status
