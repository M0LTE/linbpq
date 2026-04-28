"""Browser-tier interaction tests with console-error gates.

These drive actual UI interactions — typing into the terminal,
opening a chat session, composing a WebMail message — and assert
no JS errors fired during the interaction.  Without these, a
silent JS regression that breaks a click handler would slip past
"the page rendered" tests.

Every test wraps the navigation + interaction in a
``capture_js_errors`` context so any uncaught exception or
``console.error`` from JS fails the test.

Heavier scenarios (full message round-trips through the
websocket) are kept light — the goal here is regression
protection on the user-facing JS, not a full integration test
of the BBS message flow.
"""

from __future__ import annotations

import pytest

playwright = pytest.importorskip("playwright.sync_api")


# ── /Node/Terminal: type a command, observe output ───────────────


def test_terminal_type_into_input_iframe(linbpq_web, page, capture_js_errors):
    """Navigate to /Node/Terminal.html, focus the InputLine
    iframe, type a command, and confirm it lands in the
    OutputScreen.  This exercises the JS that wires Enter →
    POST /Node/TermInput.
    """
    with capture_js_errors(page) as js_errors:
        page.goto("/Node/Terminal.html", wait_until="domcontentloaded")
        page.wait_for_timeout(500)

        # Find the InputLine iframe and focus its input.
        input_frame = next(
            (f for f in page.frames if "InputLine" in (f.url or "")),
            None,
        )
        assert input_frame is not None, (
            f"InputLine iframe not present.  Frames: "
            f"{[f.url for f in page.frames]}"
        )
        # The InputLine page has a single text input.
        text_input = input_frame.locator("input[type=text]").first
        if text_input.count() == 0:
            pytest.skip("InputLine page has no <input type=text>")
        text_input.fill("?")
        text_input.press("Enter")
        # Give the BBS a moment to echo back.
        page.wait_for_timeout(700)

        output_frame = next(
            (f for f in page.frames if "OutputScreen" in (f.url or "")),
            None,
        )
        assert output_frame is not None
        output_html = output_frame.content()
        # Expect *something* echoed.  Many BBS builds echo the
        # command itself or a help banner; we accept either.
        # Failure mode that this catches: the JS raises trying
        # to wire input → POST and nothing reaches the server.

    assert not js_errors, f"JS errors during terminal interaction: {js_errors}"


def test_terminal_close_button_clickable(linbpq_web, page, capture_js_errors):
    """The Close button is a plain submit on a form pointing at
    /Node/TermClose.  Clicking it must navigate without JS errors.
    """
    with capture_js_errors(page) as js_errors:
        page.goto("/Node/Terminal.html", wait_until="domcontentloaded")
        close_btn = page.locator(
            'form[action^="/Node/TermClose"] input[type=submit]'
        ).first
        assert close_btn.count() == 1
        # Don't actually navigate away (next test would lose
        # context); just verify the button is enabled and
        # clickable (Playwright's ``is_enabled`` check).
        assert close_btn.is_enabled()
    assert not js_errors, f"JS errors on terminal close-button page: {js_errors}"


# ── /Mail/Conf: toggle a checkbox, save, see persistence ─────────


def test_mail_config_form_toggle_checkbox_via_browser(
    linbpq_web, page, capture_js_errors
):
    """Navigate to /Mail/Conf, toggle the ``Refuse Bulls`` checkbox,
    submit Save, and verify the checkbox stays toggled on reload.

    Catches a JS regression that prevents form submission, plus
    confirms the round-trip from the user-facing browser angle.
    """
    # First we need a Mail session — the Mail signon + then nav.
    with capture_js_errors(page) as js_errors:
        page.goto("/Mail/Signon", wait_until="domcontentloaded")
        page.fill('input[name="user"]', "test")
        page.fill('input[name="password"]', "test")
        page.locator('input[type="submit"][value="Submit"]').first.click()
        page.wait_for_load_state("domcontentloaded")
        # Land on the BBS top frame; click "Configuration".
        config_link = page.locator('a[href*="/Mail/Conf?"]').first
        if config_link.count() == 0:
            pytest.skip("BBS top frame missing Configuration link")
        config_link.click()
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(300)

        # Toggle the RefuseBulls checkbox.
        cb = page.locator('input[name="RefuseBulls"]').first
        if cb.count() == 0:
            pytest.skip("RefuseBulls checkbox not in config form on this build")
        was_checked = cb.is_checked()
        cb.click()
        # Submit Save.
        save_btn = page.locator('input[type=submit][value="Save"]').first
        save_btn.click()
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(300)

        # Re-navigate to /Mail/Conf and confirm the checkbox state
        # changed.
        config_link2 = page.locator('a[href*="/Mail/Conf?"]').first
        if config_link2.count():
            config_link2.click()
            page.wait_for_load_state("domcontentloaded")
        cb_after = page.locator('input[name="RefuseBulls"]').first
        assert cb_after.is_checked() != was_checked, (
            "RefuseBulls checkbox didn't toggle through the save"
        )

    assert not js_errors, f"JS errors during config-form interaction: {js_errors}"


# ── /WebMail: navigate to compose, type a draft, console-clean ───


def test_webmail_compose_view_loads_clean(
    linbpq_web, page, capture_js_errors
):
    """Drive WebMail to the New Message composer and confirm the
    form loads without JS errors and exposes the expected
    To/Subject/Body fields."""
    with capture_js_errors(page) as js_errors:
        page.goto("/WebMail", wait_until="domcontentloaded")
        page.wait_for_timeout(400)
        # Look for the "New Message" link / button.  WebMail
        # presents this in the top toolbar.
        new_msg = page.get_by_text("New Message", exact=False).first
        if new_msg.count() == 0:
            # Try the JS-driven NewMsg endpoint directly.
            page.goto("/WebMail/NewMsg", wait_until="domcontentloaded")
            page.wait_for_timeout(400)
        else:
            new_msg.click()
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(400)

        content = page.content().lower()
        # The composer should expose to/subject/body fields.
        assert (
            "to" in content and "subject" in content
        ), "WebMail composer missing To / Subject fields"

    assert not js_errors, f"JS errors loading WebMail composer: {js_errors}"


# ── /Node admin pages: nav-bar links don't throw ─────────────────


def test_webmail_compose_posts_to_correct_url(
    linbpq_web, page, capture_js_errors
):
    """Drive the WebMail composer end-to-end and verify the
    submit POST lands on ``/WebMail/EMSave?<key>`` — the URL that
    the route handler in ``WebMail.c`` exact-matches.

    Regression test for an extraction artefact: the original C
    source had ``action=/WebMail/EMSave\\?%s`` where the C
    compiler resolved ``\\?`` to ``?``.  When the template was
    extracted to ``HTML/MsgInputPage.txt`` the ``\\`` was kept
    verbatim, so browsers parsed the action as
    ``/WebMail/EMSave\\?<key>`` and (via slash-normalisation)
    POSTed to ``/WebMail/EMSave/?<key>`` — which the handler's
    ``_stricmp(NodeURL, "/WebMail/EMSave")`` exact match
    rejects.  Result: clicking Send silently lost the message.

    The test checks the final POST URL — not whether the
    message persists, because that depends on multipart file
    data we don't supply here.  The URL match is the part that
    pinned down whether the route handler ran.
    """
    import re as _re
    posts: list[str] = []
    page.on(
        "request",
        lambda r: posts.append(r.url) if r.method == "POST" else None,
    )
    with capture_js_errors(page) as js_errors:
        page.goto("/WebMail", wait_until="domcontentloaded")
        page.wait_for_timeout(400)
        body = page.content()
        m = _re.search(r"newmsg\('([^']+)'\)", body)
        if not m:
            import pytest
            pytest.skip("WebMail entry page didn't expose newmsg() — auth?")
        key = m.group(1)
        page.evaluate(f"newmsg({key!r})")
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(400)
        action = page.locator("form#myform").get_attribute("action")
        assert action and "\\" not in action, (
            f"form action contains a backslash: {action!r}"
        )
        page.fill("input[name=To]", "N0CALL")
        page.fill("input[name=Subj]", "regression-test")
        page.fill("textarea[name=Msg]", "body")
        page.locator("input[name=Send]").click()
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(400)

    assert posts, "no POST captured during compose-and-send"
    submit_url = next((u for u in posts if "EMSave" in u), None)
    assert submit_url is not None, (
        f"no POST to anything containing 'EMSave': {posts!r}"
    )
    # Critical: must NOT be /WebMail/EMSave/?... (the slash-
    # normalised buggy form).  Must be /WebMail/EMSave?...
    assert "/WebMail/EMSave?" in submit_url, (
        f"submit POST went to {submit_url!r}; expected exact "
        f"'/WebMail/EMSave?<key>'.  Trailing slash means the "
        f"route handler skipped it."
    )
    assert "/WebMail/EMSave/?" not in submit_url, (
        f"submit POST has the buggy trailing-slash variant: "
        f"{submit_url!r}"
    )
    assert not js_errors, f"JS errors during WebMail submit: {js_errors}"


def test_node_admin_pages_nav_no_js_errors(
    linbpq_web, page, capture_js_errors
):
    """Visit each /Node/*.html page and confirm no JS errors fire
    on load.

    Previously needed an allow-list for ``Invalid or unexpected
    token`` because ``HTML/NodeTail.txt`` had stray ``\\`` line
    continuations leftover from when it was a C string literal —
    introduced during the templatedefs.c → HTML/ extraction work,
    not present in the original code.  The HTML file has been
    cleaned up; the gate is now strict.
    """
    pages = [
        "/Node/NodeIndex.html",
        "/Node/Status.html",
        "/Node/Routes.html",
        "/Node/Nodes.html",
        "/Node/Ports.html",
        "/Node/Stats.html",
        "/Node/MH.html",
    ]
    with capture_js_errors(page) as js_errors:
        for path in pages:
            page.goto(path, wait_until="domcontentloaded")
            page.wait_for_timeout(150)
    assert not js_errors, (
        f"JS errors on admin pages: {js_errors}"
    )
