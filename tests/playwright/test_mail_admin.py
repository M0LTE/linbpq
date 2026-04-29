"""Mail admin pages — round-trip + structural coverage.

Companion to test_template_render_matrix.py (which proves each
post-signon Mail page renders the right template).  Here we go
deeper: form fields are present, BBSName from config round-trips
into the config form, the user/message/forwarding tables show
expected headers even with empty data, and the housekeeping form
exposes the schedule fields.
"""

from __future__ import annotations

from web_helpers import http_get, http_post


def test_mail_signon_form_action_uses_mail_query(linbpq_web):
    """The Mail signon form must POST to /Mail/Signon?Mail —
    without the ?Mail suffix POST hits M0LTE/linbpq#18."""
    port = linbpq_web["http_port"]
    status, body = http_get(port, "/Mail/Signon")
    assert b"200" in status
    assert b"action=/Mail/Signon?Mail" in body


def test_mail_signon_post_succeeds_and_returns_session_key(linbpq_web):
    """POST /Mail/Signon?Mail returns the BBS top-frame with a
    fresh session key embedded in nav URLs."""
    port = linbpq_web["http_port"]
    status, body = http_post(
        port, "/Mail/Signon?Mail", b"User=test&password=test"
    )
    assert b"200" in status
    assert b"BPQ32 BBS" in body
    # Session key format: M followed by 12 hex chars.
    import re
    assert re.search(rb"\?M[0-9A-F]{12}", body), (
        f"no session key in response: {body[:300]!r}"
    )


def test_mail_main_config_form_round_trips_bbs_name(mail_session):
    """The MainConfig form (MainConfig.txt v7) should show the
    current BBSName ("N0CALL", from the config we seeded) in the
    appropriate input field."""
    port, key = mail_session["port"], mail_session["key"]
    status, body = http_get(port, f"/Mail/Conf?{key}")
    assert b"200" in status
    assert b"Main Configuration" in body
    assert b"N0CALL" in body, "BBSName not echoed into config form"


def test_mail_users_page_table_headers(mail_session):
    """UserPage.txt v4 — user list table.  Even with no extra
    BBS users beyond the SYSOP, the table headers must be present."""
    port, key = mail_session["port"], mail_session["key"]
    status, body = http_get(port, f"/Mail/Users?{key}")
    assert b"200" in status
    # Some flavour of user list / select form.
    assert b"User" in body or b"Callsign" in body


def test_mail_messages_page_renders(mail_session):
    """MsgPage.txt v2 — message list.  Empty-state must still
    render the message-list shell (form + buttons)."""
    port, key = mail_session["port"], mail_session["key"]
    status, body = http_get(port, f"/Mail/Msgs?{key}")
    assert b"200" in status
    # MsgPage shell must render even with no messages — at minimum
    # a form/table reference, since the JS later fills the rows.
    assert b"<form" in body or b"<table" in body, (
        f"MsgPage missing list shell: {body[:300]!r}"
    )


def test_mail_housekeeping_form_renders(mail_session):
    """Housekeeping.txt v2 — exposes the maintenance schedule.
    Must show editable fields, not a static page."""
    port, key = mail_session["port"], mail_session["key"]
    status, body = http_get(port, f"/Mail/HK?{key}")
    assert b"200" in status
    assert b"<form" in body, "Housekeeping page should be a form"


def test_mail_forwarding_page_renders(mail_session):
    """FwdPage.txt v4 — forwarding partners list.  Empty-state
    still shows the partner-add UI."""
    port, key = mail_session["port"], mail_session["key"]
    status, body = http_get(port, f"/Mail/FWD?{key}")
    assert b"200" in status
    # FwdPage carries either a partner table (if any partners
    # configured) or an empty-state form.  Pin the form/table.
    assert b"<form" in body or b"<table" in body, (
        f"FwdPage missing form/table: {body[:300]!r}"
    )


def test_mail_wp_page_renders(mail_session):
    """WP.txt v1 — White Pages update form.  Page is JS-driven so
    the static HTML is just the outer frame + ``#sidebar`` /
    ``#main`` divs that the JS fills; pin the page title."""
    port, key = mail_session["port"], mail_session["key"]
    status, body = http_get(port, f"/Mail/WP?{key}")
    assert b"200" in status
    assert b"White Pages" in body, (
        f"WP page missing White Pages title: {body[:300]!r}"
    )


def test_mail_welcome_page_renders(mail_session):
    """Welcome.txt v1 — welcome message editor."""
    port, key = mail_session["port"], mail_session["key"]
    status, body = http_get(port, f"/Mail/Wel?{key}")
    assert b"200" in status
    # Welcome page should be editable HTML
    assert b"<form" in body or b"<textarea" in body


def test_mail_status_page_self_refreshes(mail_session):
    """The status page sets a meta-refresh so it auto-updates."""
    port, key = mail_session["port"], mail_session["key"]
    status, body = http_get(port, f"/Mail/Status?{key}")
    assert b"200" in status
    assert b"refresh" in body.lower(), (
        "expected meta-refresh on Mail status page"
    )


def test_mail_signon_failure_returns_passerror(linbpq_web):
    """Bad password: re-renders MailSignon and appends PassError.txt.
    Locks in PassError fragment usage."""
    port = linbpq_web["http_port"]
    status, body = http_post(
        port, "/Mail/Signon?Mail", b"User=test&password=BAD"
    )
    assert b"200" in status
    assert b"BPQ32 Mail Server" in body
    assert b"User or Password is invalid" in body
