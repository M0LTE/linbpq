"""Tests that assert real data renders — using the seeded fixture.

These prove the table renderers work with non-empty state.  Without
seeded data, the existing table-header tests pass against an empty
BBS — a renderer that breaks specifically when a row exists would
slip through.

Coverage (with linbpq_web_seeded yielding 3 added BBS users and a
best-effort attempt at 3 messages via telnet):

- POST /Mail/UserList.txt returns each seeded callsign.
- /Mail/Users renders the user list page with the JS callout to
  UserList.txt.
- The BBS user count (visible from Mail/Status) reflects the
  seeded users.
"""

from __future__ import annotations

from web_helpers import fetch_user_list, http_get


def test_seeded_users_appear_in_user_list(linbpq_web_seeded):
    """The /Mail/UserList.txt data feed must include every
    callsign we added during fixture setup."""
    port, key = linbpq_web_seeded["http_port"], linbpq_web_seeded["key"]
    users = fetch_user_list(port, key)
    for call in linbpq_web_seeded["users"]:
        assert call in users, (
            f"seeded user {call!r} missing from /Mail/UserList.txt: "
            f"got {users!r}"
        )


def test_seeded_users_count_at_least_baseline(linbpq_web_seeded):
    """The user list has the SYSOP (auto-created from BBSCALL) plus
    every seeded user.  Lower-bound on the count guards against a
    renderer that drops rows."""
    port, key = linbpq_web_seeded["http_port"], linbpq_web_seeded["key"]
    users = fetch_user_list(port, key)
    # SYSOP (N0CALL) + 3 seeded = 4 minimum.
    assert len(users) >= len(linbpq_web_seeded["users"]) + 1, (
        f"expected ≥{len(linbpq_web_seeded['users']) + 1} users, "
        f"got {len(users)}: {users!r}"
    )


def test_users_page_renders_with_real_data(linbpq_web_seeded):
    """The Mail/Users page is JS-driven — its initial HTML is the
    same skeleton even with data, but it must reference the
    UserList.txt endpoint that actually carries the data."""
    port, key = linbpq_web_seeded["http_port"], linbpq_web_seeded["key"]
    status, body = http_get(port, f"/Mail/Users?{key}")
    assert b"200" in status
    assert b"<!-- Version 4" in body[:80]
    assert b"GetData" in body, "users page missing JS data-loader"


def test_user_details_form_for_seeded_call(linbpq_web_seeded):
    """``POST /Mail/UserDetails`` with a seeded callsign loads
    that user's edit form.  Locks in the lookup-by-call path."""
    port, key = linbpq_web_seeded["http_port"], linbpq_web_seeded["key"]
    target = linbpq_web_seeded["users"][0]
    from web_helpers import http_post

    status, body = http_post(
        port, f"/Mail/UserDetails?{key}", target.encode("ascii")
    )
    assert b"200" in status
    assert target.encode("ascii") in body, (
        f"UserDetails for {target} doesn't reference the call: {body[:200]!r}"
    )
    # The form must have the BBS / SYSOP / Expert checkboxes — the
    # fixed shape of UserDetail.txt.
    assert b'name="BBS"' in body
    assert b'name="SYSOP"' in body


def test_seeded_messages_appear_in_msg_store(linbpq_web_seeded):
    """Verify that messages sent during fixture setup via the
    telnet ``S TO/title/body/EX`` flow show up in the BBS message
    store.

    The data model is two-level:
    - ``POST /Mail/MsgInfo.txt`` returns a ``|``-separated list of
      message numbers matching an optional filter.
    - ``POST /Mail/MsgDetails`` with a message number returns the
      detail form, which embeds From/To/Subject.

    We accept any one of the seeded subjects appearing in any of
    the message details — partial success counts, since telnet
    seeding is best-effort and one or two messages may have
    failed to round-trip.
    """
    if not linbpq_web_seeded["messages"]:
        import pytest
        pytest.skip("no messages seeded (telnet timing) — see fixture")
    port, key = linbpq_web_seeded["http_port"], linbpq_web_seeded["key"]
    from web_helpers import http_post

    status, body = http_post(port, f"/Mail/MsgInfo.txt?{key}", b"")
    assert b"200" in status
    # Parse the message-number list out of the response.
    text = body.split(b"<!--", 1)[0].decode("ascii", "replace")
    msg_nums = [int(n) for n in text.split("|") if n.strip().isdigit()]
    assert msg_nums, (
        f"/Mail/MsgInfo.txt returned no message numbers — seeding failed.  "
        f"body: {body[:200]!r}"
    )

    # Pull each message's details and look for the seeded subjects.
    seeded_subjects = [m["subject"].encode("ascii") for m in linbpq_web_seeded["messages"]]
    found = []
    for n in msg_nums:
        status, detail = http_post(
            port, f"/Mail/MsgDetails?{key}", str(n).encode("ascii")
        )
        if b"200" not in status:
            continue
        for subject in seeded_subjects:
            if subject in detail:
                found.append(subject)
    assert found, (
        f"none of the seeded subjects {seeded_subjects!r} found in any of "
        f"the {len(msg_nums)} stored messages.  msg_nums: {msg_nums}"
    )
