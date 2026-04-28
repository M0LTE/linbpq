"""Round-trip POST→GET form persistence tests.

For each major settings form, POST a tweaked value, GET the page
back, assert the new value persists.  Without these, "the form
renders" doesn't tell us "the form actually saves what you type."

Coverage:
- /Mail/Welcome — welcome message round-trips into the textarea.
- /Chat/ChatConfig — chat welcome message round-trips.
- /Mail/UserSave (Add=) → /Mail/UserList.txt — adding a user
  shows up in the list (also covered in test_seeded_data, here
  as a direct round-trip).
"""

from __future__ import annotations

import urllib.parse

from web_helpers import http_get, http_post, fetch_user_list


def _urlencode(form: dict) -> bytes:
    """Form-encode without depending on requests."""
    return urllib.parse.urlencode(form).encode("ascii")


# ── Mail welcome message round-trip ──────────────────────────────


def test_mail_welcome_message_round_trips(mail_session):
    """POST /Mail/Welcome with a recognisable welcome string,
    then GET /Mail/Wel and verify the new value is in the form
    textarea."""
    port, key = mail_session["port"], mail_session["key"]
    sentinel = "PLAYWRIGHT_TEST_WELCOME_MARKER"
    body = _urlencode(
        {
            "NUWelcome": f"{sentinel} for new users.",
            "NewWelcome": "",
            "ExWelcome": "",
            "NUPrompt": "node>",
            "NewPrompt": "node>",
            "ExPrompt": "node>",
            "Bye": "73",
            "Update": "Update",
        }
    )
    status, _ = http_post(port, f"/Mail/Welcome?{key}", body)
    assert b"200" in status, f"POST /Mail/Welcome: {status!r}"

    # Fetch the form back; the saved welcome must be there.
    status, form = http_get(port, f"/Mail/Wel?{key}")
    assert b"200" in status
    assert sentinel.encode("ascii") in form, (
        f"welcome marker {sentinel!r} not in /Mail/Wel form: {form[:400]!r}"
    )


# ── User-add round-trip ──────────────────────────────────────────


def test_user_add_round_trip(mail_session):
    """``Add=<call>`` to /Mail/UserSave creates a user, which is
    then visible in the /Mail/UserList.txt feed."""
    port, key = mail_session["port"], mail_session["key"]
    new_call = "M0RTRP"

    status, _ = http_post(
        port,
        f"/Mail/UserSave?{key}",
        f"Add={new_call}".encode("ascii"),
    )
    assert b"200" in status

    users = fetch_user_list(port, key)
    assert new_call in users, (
        f"newly-added {new_call!r} not in /Mail/UserList.txt: {users!r}"
    )


# ── Chat welcome message round-trip ──────────────────────────────


def test_chat_welcome_message_round_trips(chat_session):
    """POST /Chat/ChatConfig with a tweaked welcome message, then
    GET /Chat/ChatConf and verify it appears in the form textarea.

    The handler reads field name ``welcome=`` (lowercase) — see
    ChatHTMLConfig.c::ChatConfig.
    """
    port, key = chat_session["port"], chat_session["key"]
    sentinel = "PWTESTCHATWELCOME"  # No underscores — server may HTML-escape
    body = _urlencode(
        {
            "ApplNum": "2",
            "Streams": "10",
            "Paclen": "60",
            "Posn": "",
            "PopType": "Hover",
            "MapText": "",
            "welcome": sentinel,
            "nodes": "",
            "Save": "Save",
        }
    )
    status, _ = http_post(port, f"/Chat/ChatConfig?{key}", body)
    assert b"200" in status

    status, form = http_get(port, f"/Chat/ChatConf?{key}")
    assert b"200" in status
    assert sentinel.encode("ascii") in form, (
        f"chat welcome {sentinel!r} not in /Chat/ChatConf form: {form[:600]!r}"
    )


# ── Mail housekeeping schedule round-trip ────────────────────────


def test_mail_housekeeping_field_round_trips(mail_session):
    """POST /Mail/HK with tweaked housekeeping params, GET back,
    confirm the changed value persists.

    The housekeeping form has many numeric scheduling fields;
    we tweak ``MaxAge`` (message retention days) which is
    rendered into a numeric input."""
    port, key = mail_session["port"], mail_session["key"]
    test_value = "47"  # Distinctive — not any default
    # Capture the form first so we know the existing values to
    # echo back unchanged.
    status, form_before = http_get(port, f"/Mail/HK?{key}")
    assert b"200" in status

    # POST with a tweaked MaxAge.  We don't know all the form's
    # fields, so we send only the ones we want to set; the
    # handler (SaveHousekeeping) reads named params via
    # GetParam — extra fields are ignored, missing ones default.
    body = _urlencode(
        {
            "MaxAge": test_value,
            "Update": "Update",
        }
    )
    status, _ = http_post(port, f"/Mail/HK?{key}", body)
    assert b"200" in status

    status, form_after = http_get(port, f"/Mail/HK?{key}")
    assert b"200" in status
    # The new value should appear as the value attribute of the
    # MaxAge input.  Search for it as ``value="47"`` or ``value='47'``.
    expected_patterns = [
        f'value="{test_value}"'.encode("ascii"),
        f"value='{test_value}'".encode("ascii"),
        f">{test_value}<".encode("ascii"),
    ]
    assert any(p in form_after for p in expected_patterns), (
        f"MaxAge={test_value} did not round-trip into /Mail/HK form.  "
        f"Looked for {expected_patterns!r}; form snippet: "
        f"{form_after[:600]!r}"
    )


# ── /Mail/Config HRoute round-trip ───────────────────────────────


def test_mail_config_hroute_round_trips(mail_session):
    """POST /Mail/Config with a tweaked HRoute, GET the config
    form back, assert the new HRoute appears in the rendered
    ``value="..."`` attribute.

    Note: must GET /Mail/Conf at least once before the POST.  The
    config save handler reads the ``ConfigTemplate`` global which
    only gets initialised on the first /Mail/Conf request; without
    it the post-save form-render NULL-derefs.  Real users always
    open the config page before saving, so this matches normal
    usage — just lock the order in here.
    """
    port, key = mail_session["port"], mail_session["key"]

    # Prime the ConfigTemplate global by loading the form first.
    status, _ = http_get(port, f"/Mail/Conf?{key}")
    assert b"200" in status

    sentinel = "TESTHR1"
    body = _urlencode(
        {"HRoute": sentinel, "BBSCall": "N0CALL", "Save": "Save"}
    )
    status, _ = http_post(port, f"/Mail/Config?{key}", body)
    assert b"200" in status, f"/Mail/Config POST: {status!r}"

    status, form_after = http_get(port, f"/Mail/Conf?{key}")
    assert b"200" in status
    assert sentinel.encode("ascii") in form_after, (
        f"HRoute={sentinel} did not round-trip into /Mail/Conf form.  "
        f"Last 800 chars of form: {form_after[-800:]!r}"
    )
