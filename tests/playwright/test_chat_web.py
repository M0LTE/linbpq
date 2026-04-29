"""Chat HTTP coverage.

Builds on the Chat post-signon walkthrough in
test_template_extraction.py with deeper checks on each Chat
endpoint: status table contents, configuration form fields,
config-save round-trip, the Chat session page (Chat.html), and
the disconnect endpoint.
"""

from __future__ import annotations

from web_helpers import http_get, http_post


def test_chat_signon_form_action_uses_chat_query(linbpq_web):
    """The Chat signon form must POST to /Chat/Signon?Chat — without
    the ?Chat suffix, ProcessChatSignon hits the same NULL-Appl
    pattern as the Mail bug (M0LTE/linbpq#18 sibling)."""
    port = linbpq_web["http_port"]
    status, body = http_get(port, "/Chat/Signon")
    assert b"200" in status
    assert b"action=/Chat/Signon?Chat" in body


def test_chat_status_renders(chat_session):
    """ChatStatus.txt — server status / connected nodes table."""
    port, key = chat_session["port"], chat_session["key"]
    status, body = http_get(port, f"/Chat/ChatStatus?{key}")
    assert b"200" in status
    # Status page should include the Status / Configuration / Node Menu
    # nav row even if the status table is empty.
    assert b"Status" in body
    assert b"Configuration" in body or b"Config" in body


def test_chat_config_form_renders(chat_session):
    """ChatConfig.txt v2 — chat config form shows current values
    we seeded in chatconfig.cfg."""
    port, key = chat_session["port"], chat_session["key"]
    status, body = http_get(port, f"/Chat/ChatConf?{key}")
    assert b"200" in status
    assert b"Chat Configuration" in body
    # Welcome message we seeded should round-trip into the form.
    assert b"Welcome to the test chat node" in body, (
        f"chat welcome msg not round-tripped to form: {body[:400]!r}"
    )


def test_chat_chat_html_renders_session_page(chat_session):
    """/Chat/Chat.html serves the chat-session frame (ChatPage.txt
    rendered for the live session)."""
    port, key = chat_session["port"], chat_session["key"]
    status, body = http_get(port, f"/Chat/Chat.html?{key}")
    assert b"200" in status
    # ChatPage v1 wraps with N0CALL-2's Chat Server title.
    assert b"Chat" in body


def test_chat_dis_session_returns_html(chat_session):
    """``/Chat/ChatDisSession?<key>`` triggers the disconnect
    endpoint.  Should 200 with an HTML response (server-side it
    closes the chat session and returns the status page)."""
    port, key = chat_session["port"], chat_session["key"]
    status, body = http_get(port, f"/Chat/ChatDisSession?{key}")
    assert b"200" in status
    assert b"<" in body[:50]
