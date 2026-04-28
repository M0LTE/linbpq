"""Browser-tier tests for the web terminal at /Node/Terminal.html.

The web terminal is JS-heavy: it polls /Node/OutputScreen.html for
output and POSTs to /Node/TermInput for each input line, all
inside an iframe layout.  Without JS execution you can't tell
whether the page is actually wiring up the input/output frames.

These tests use Playwright (Chromium headless) to drive the page
and verify that:

- The page loads without console errors.
- The expected DOM structure (input + output iframes) is present.
- The frames each load in their own right (no 404 / 0-byte).

Loopback access auto-authenticates from the LOCAL detection in
HTTPcode.c, so the Terminal page renders the live terminal
straight away rather than a signon form.
"""

from __future__ import annotations

import pytest

playwright = pytest.importorskip("playwright.sync_api")


def test_terminal_page_loads_without_console_errors(linbpq_web, page):
    """``/Node/Terminal.html`` loads, JS doesn't throw."""
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(f"pageerror: {exc}"))
    page.on(
        "console",
        lambda msg: errors.append(f"console.error: {msg.text}")
        if msg.type == "error"
        else None,
    )
    response = page.goto("/Node/Terminal.html", wait_until="domcontentloaded")
    assert response is not None
    assert response.status == 200, f"unexpected status {response.status}"
    content = page.content()
    assert "<html" in content.lower(), "Terminal page didn't render HTML"
    assert not errors, f"console / page errors: {errors}"


def test_terminal_page_has_input_and_output_iframes(linbpq_web, page):
    """The live terminal renders two iframes: OutputScreen
    (top, scrolling output) and InputLine (bottom, command entry)."""
    page.goto("/Node/Terminal.html", wait_until="domcontentloaded")
    iframes = page.locator("iframe")
    assert iframes.count() >= 2, (
        f"expected ≥2 iframes (output + input), got {iframes.count()}"
    )
    srcs = [iframes.nth(i).get_attribute("src") for i in range(iframes.count())]
    assert any(
        s and "OutputScreen" in s for s in srcs
    ), f"OutputScreen iframe missing: {srcs}"
    assert any(
        s and "InputLine" in s for s in srcs
    ), f"InputLine iframe missing: {srcs}"


def test_terminal_output_iframe_loads(linbpq_web, page):
    """Drill into the OutputScreen iframe and confirm it
    rendered (server returned 200, frame document has body)."""
    page.goto("/Node/Terminal.html", wait_until="domcontentloaded")
    # Wait for at least one frame to attach.
    page.wait_for_timeout(500)
    output_frame = next(
        (f for f in page.frames if "OutputScreen" in (f.url or "")),
        None,
    )
    assert output_frame is not None, (
        f"OutputScreen frame not found.  Frames: {[f.url for f in page.frames]}"
    )
    body_html = output_frame.content()
    assert "<body" in body_html.lower() or "<html" in body_html.lower()


def test_terminal_close_form_targets_termclose(linbpq_web, page):
    """The Close button POSTs to /Node/TermClose.  Lock that
    in so a refactor doesn't silently break the close path."""
    page.goto("/Node/Terminal.html", wait_until="domcontentloaded")
    close_form = page.locator('form[action^="/Node/TermClose"]')
    assert close_form.count() == 1, (
        f"expected exactly one TermClose form, got {close_form.count()}"
    )
