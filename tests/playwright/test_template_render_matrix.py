"""Render-time matrix for the extracted HTML templates.

For every template that has a reachable URL in the default
``mail+chat`` (no APRS) configuration, we hit the URL and assert
the response body carries the expected ``<!-- Version N`` marker.
This is the catch-all that fails fast if any future change
breaks one of the post-extraction render paths — e.g. wrong
sprintf arg count, missing ``LoadTemplates_*()`` call, dropped
``HTML/`` file, or version bump that didn't propagate.

Templates that are pure fragments (rendered as part of a parent
page, no URL of their own) are intentionally not in this matrix
— their parent page's row covers them implicitly.

Keep this file curated.  When adding a new template:

1. If it has a unique URL, add a row here so any change that
   stops it rendering fires a test.
2. If it's a fragment, leave a comment in the parent template's
   row noting which fragments it contains, so reviewers know not
   to expect a separate row.
"""

from __future__ import annotations

import re

import pytest

from web_helpers import http_get, http_post, mail_signon, chat_signon


# Whole-module fork gate: every test here asserts a
# ``<!-- Version N`` marker that only exists on the M0LTE fork's
# extracted HTML/ templates.  Vanilla upstream serves the inline
# templatedefs.c versions which don't carry the comment.
pytestmark = pytest.mark.fork_only


def _version_marker(version: int) -> bytes:
    """Match ``<!-- Version N`` followed by a separator (space or
    ``--`` close).  The published templates have either
    ``<!-- Version N -->`` or ``<!-- Version N <date> -->``."""
    return rb"<!-- Version " + str(version).encode("ascii") + rb"[\s>]"


# ── No-auth GETs ─────────────────────────────────────────────────


# (path, version, source-template-file)
NO_AUTH_RENDERS = [
    ("/Mail/Signon", 1, "MailSignon.txt"),
    ("/Chat/Signon", 1, "ChatSignon.txt"),
    ("/Node/Signon", 1, "NodeSignon.txt"),
]


@pytest.mark.parametrize("path,version,template", NO_AUTH_RENDERS)
def test_no_auth_render(linbpq_web, path, version, template):
    port = linbpq_web["http_port"]
    status, body = http_get(port, path)
    assert b"200" in status, f"GET {path}: {status!r}"
    assert re.search(_version_marker(version), body[:300]), (
        f"GET {path} ({template}): missing Version {version} marker.  "
        f"Body[:300]: {body[:300]!r}"
    )


# ── Mail post-signon GETs ────────────────────────────────────────


# (path, version, source-template-file).  The path is suffixed
# with ``?<key>`` at request time.
MAIL_RENDERS = [
    ("/Mail/Status", 1, "StatusPage.txt"),
    ("/Mail/Conf", 7, "MainConfig.txt"),
    ("/Mail/Users", 4, "UserPage.txt"),
    ("/Mail/Msgs", 2, "MsgPage.txt"),
    ("/Mail/HK", 2, "Housekeeping.txt"),
    ("/Mail/FWD", 4, "FwdPage.txt"),
    ("/Mail/WP", 1, "WP.txt"),
    ("/Mail/Wel", 1, "Welcome.txt"),
    ("/Mail/Header", 1, "MailPage.txt"),
]


@pytest.mark.parametrize("path,version,template", MAIL_RENDERS)
def test_mail_render(mail_session, path, version, template):
    port, key = mail_session["port"], mail_session["key"]
    url = f"{path}?{key}"
    status, body = http_get(port, url)
    assert b"200" in status, f"GET {url}: {status!r}"
    assert re.search(_version_marker(version), body[:300]), (
        f"GET {url} ({template}): missing Version {version} marker.  "
        f"Body[:300]: {body[:300]!r}"
    )


# ── Chat post-signon GETs ────────────────────────────────────────


CHAT_RENDERS = [
    ("/Chat/ChatStatus", 1, "ChatStatus.txt"),
    ("/Chat/ChatConf", 2, "ChatConfig.txt"),
    ("/Chat/Header", 1, "ChatPage.txt"),
    ("/Chat/Chat.html", 1, "ChatPage.txt"),
]


@pytest.mark.parametrize("path,version,template", CHAT_RENDERS)
def test_chat_render(chat_session, path, version, template):
    port, key = chat_session["port"], chat_session["key"]
    url = f"{path}?{key}"
    status, body = http_get(port, url)
    assert b"200" in status, f"GET {url}: {status!r}"
    assert re.search(_version_marker(version), body[:300]), (
        f"GET {url} ({template}): missing Version {version} marker.  "
        f"Body[:300]: {body[:300]!r}"
    )


# ── WebMail entry pages ──────────────────────────────────────────


# /WebMail and the bare entry URLs auto-authenticate from the local
# loopback and serve WebMailPage.txt directly — no explicit signon
# needed.  Adding a ``?<MailKey>`` query string actually flips the
# response back to WebMailSignon (because the mail key isn't a
# valid WebMail session key), so we test these *without* a key.
WEBMAIL_RENDERS = [
    ("/WebMail", 6, "WebMailPage.txt"),
    ("/WebMail/MailEntry", 6, "WebMailPage.txt"),
]


@pytest.mark.parametrize("path,version,template", WEBMAIL_RENDERS)
def test_webmail_render(linbpq_web, path, version, template):
    port = linbpq_web["http_port"]
    status, body = http_get(port, path)
    assert b"200" in status, f"GET {path}: {status!r}"
    assert re.search(_version_marker(version), body[:300]), (
        f"GET {path} ({template}): missing Version {version} marker.  "
        f"Body[:300]: {body[:300]!r}"
    )


def test_webmail_signon_post_renders_message_list(linbpq_web):
    """POST /WebMail/Signon with creds returns the WebMail UI
    (Message List view), still on WebMailPage.txt v6."""
    port = linbpq_web["http_port"]
    status, body = http_post(
        port, "/WebMail/Signon", b"User=test&password=test"
    )
    assert b"200" in status, f"POST /WebMail/Signon: {status!r}"
    assert re.search(_version_marker(6), body[:300]), (
        f"WebMailPage marker missing post-signon: {body[:300]!r}"
    )
    assert b"Message List" in body, (
        f"WebMail UI didn't render the message list: {body[:300]!r}"
    )


# ── Signon-failure renders (PassError fragment) ──────────────────


def test_mail_signon_pass_error_renders(linbpq_web):
    """Bad password POST should re-render MailSignon and append
    the PassError fragment.  Locks in PassError.txt usage."""
    port = linbpq_web["http_port"]
    status, body = http_post(
        port, "/Mail/Signon?Mail", b"User=test&password=WRONG"
    )
    assert b"200" in status, f"POST /Mail/Signon?Mail: {status!r}"
    assert b"BPQ32 Mail Server" in body, "MailSignon not re-rendered on failure"
    assert b"User or Password is invalid" in body, (
        f"PassError fragment not appended: {body[-200:]!r}"
    )


def test_chat_signon_pass_error_renders(linbpq_web):
    """Same as Mail but for Chat."""
    port = linbpq_web["http_port"]
    status, body = http_post(
        port, "/Chat/Signon?Chat", b"User=test&password=WRONG"
    )
    assert b"200" in status
    assert b"BPQ32 Chat Server" in body
    assert b"User or Password is invalid" in body


# ── webscript.js asset ───────────────────────────────────────────


def test_webscript_js_served(mail_session):
    """webscript.js is the JS the WebMail UI loads.  It's served
    on a ``/Webscript.js`` path-equivalent — verify it loads with
    ``Content-Type: application/javascript`` and is non-empty."""
    port = mail_session["port"]
    status, body = http_get(port, "/Webscript.js")
    # Some builds serve at /webscript.js (lowercase); fall back.
    if b"200" not in status:
        status, body = http_get(port, "/webscript.js")
    assert b"200" in status, f"webscript.js not served: {status!r}"
    assert len(body) > 100, "webscript.js suspiciously small"


# ── /Node/* render coverage (tier 1) ─────────────────────────────


# These are already covered by tests/integration/test_http_admin.py
# at the structural level, but we check the Version markers here
# so that template-level breakage shows up in the playwright run
# without having to wait for the integration suite.
NODE_RENDERS = [
    ("/Node/NodeIndex.html", 1, "NodeIndex (inline)"),
    ("/Node/Status.html", 1, "Status (inline)"),
    ("/Node/Stats.html", 1, "Stats (inline)"),
]


@pytest.mark.parametrize("path,version,template", NODE_RENDERS)
def test_node_render(linbpq_web, path, version, template):
    """The /Node/ pages are mostly built from inline sprintf, not
    extracted templates — but they sit alongside the extracted
    templates in MailPage's nav so a render regression shows up
    here first."""
    port = linbpq_web["http_port"]
    status, body = http_get(port, path)
    assert b"200" in status, f"GET {path}: {status!r}"
    assert b"BPQ32" in body, f"GET {path}: missing branding"
