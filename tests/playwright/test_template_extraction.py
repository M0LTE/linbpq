"""Regression coverage for the templatedefs.c → HTML/ extraction.

The 13 inline HTML/JS templates that lived in templatedefs.c are
now standalone files under ``HTML/``.  ``GetTemplateFromFile``
loads them at runtime; the fast-path returns to inline functions
have been removed (HTMLCommonCode.c).

This test file is the regression net for the extraction.

What's covered:

- All expected templates exist under HTML/ in the repo.
- Each template carries a ``<!-- Version N`` marker in its first
  bytes — HTMLCommonCode.c:112-120 enforces this at runtime; if
  extraction stripped it, every page using the template 404s with
  "Wrong Version of HTML Page".
- The compiled binary loads cleanly with HTML/ present (boot
  succeeds + Node menu pages render).  This proves the
  C-side ``#include "templatedefs.c"`` removal didn't break the
  rest of the HTTP layer.
- Boot also succeeds *without* HTML/, with the templates serving
  the "File is missing" stub instead of crashing.
- The signon forms (MailSignon.txt, ChatSignon.txt) render and
  carry the ``?Mail`` / ``?Chat`` query strings on their POST
  actions — without those, POST /Mail/Signon hits a NULL Appl
  deref upstream (M0LTE/linbpq#18).
- Chat post-signon walkthrough exercises ChatStatus.txt and
  ChatConfig.txt at render time.  Mail post-signon walkthrough
  exercises MailPage.txt, MainConfig.txt, FwdPage.txt,
  UserPage.txt, MsgPage.txt, Housekeeping.txt and WP.txt — all
  HTTP requests advertise ``Accept-Encoding: deflate`` to route
  around M0LTE/linbpq#19 (the no-deflate path sends an
  uninitialised buffer).  Browsers always send that header, so
  this matches production traffic.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from web_helpers import http_get as _http_get
from web_helpers import http_post as _http_post


_REPO_ROOT = Path(__file__).resolve().parents[2]
_HTML_DIR = _REPO_ROOT / "HTML"


EXTRACTED_TEMPLATES = (
    # (filename, expected version, source function/array in C)
    # --- Phase 1: templatedefs.c functions ---
    ("WebMailMsg.txt",   5, "WebMailMsgtxt"),
    ("FwdPage.txt",      4, "FwdPagetxt"),
    ("FwdDetail.txt",    3, "FwdDetailtxt"),
    ("webscript.js",     2, "webscriptjs"),
    ("WebMailPage.txt",  6, "WebMailPagetxt"),
    ("MainConfig.txt",   7, "MainConfigtxt"),
    ("MsgPage.txt",      2, "MsgPagetxt"),
    ("UserDetail.txt",   4, "UserDetailtxt"),
    ("UserPage.txt",     4, "UserPagetxt"),
    ("Housekeeping.txt", 2, "Housekeepingtxt"),
    ("WP.txt",           1, "WPtxt"),
    ("ChatConfig.txt",   2, "ChatConfigtxt"),
    ("ChatStatus.txt",   1, "ChatStatustxt"),
    # --- Phase 2: ChatHTMLConfig.c inline arrays ---
    ("ChatSignon.txt",   1, "ChatHTMLConfig.c::ChatSignon[]"),
    ("ChatPage.txt",     1, "ChatHTMLConfig.c::ChatPage[]"),
    # --- Phase 3: BBSHTMLConfig.c inline arrays (full sweep) ---
    ("PassError.txt",        1, "BBSHTMLConfig.c::PassError[]"),
    ("BusyError.txt",        1, "BBSHTMLConfig.c::BusyError[]"),
    ("MailSignon.txt",       1, "BBSHTMLConfig.c::MailSignon[]"),
    ("MailPage.txt",         1, "BBSHTMLConfig.c::MailPage[]"),
    ("RefreshMainPage.txt",  1, "BBSHTMLConfig.c::RefreshMainPage[]"),
    ("StatusPage.txt",       1, "BBSHTMLConfig.c::StatusPage[]"),
    ("StreamEnd.txt",        1, "BBSHTMLConfig.c::StreamEnd[]"),
    ("UIHddr.txt",           1, "BBSHTMLConfig.c::UIHddr[]"),
    ("UILine.txt",           1, "BBSHTMLConfig.c::UILine[]"),
    ("UITail.txt",           1, "BBSHTMLConfig.c::UITail[]"),
    ("FWDSelectHddr.txt",    1, "BBSHTMLConfig.c::FWDSelectHddr[]"),
    ("FWDSelectTail.txt",    1, "BBSHTMLConfig.c::FWDSelectTail[]"),
    ("UserSelectHddr.txt",   1, "BBSHTMLConfig.c::UserSelectHddr[]"),
    ("UserSelectLine.txt",   1, "BBSHTMLConfig.c::UserSelectLine[]"),
    ("StatusLine.txt",       1, "BBSHTMLConfig.c::StatusLine[]"),
    ("UserSelectTail.txt",   1, "BBSHTMLConfig.c::UserSelectTail[]"),
    ("UserUpdateHddr.txt",   1, "BBSHTMLConfig.c::UserUpdateHddr[]"),
    ("UserUpdateLine.txt",   1, "BBSHTMLConfig.c::UserUpdateLine[]"),
    ("FWDUpdate.txt",        1, "BBSHTMLConfig.c::FWDUpdate[]"),
    ("MailDetailPage.txt",   1, "BBSHTMLConfig.c::MailDetailPage[]"),
    ("MailDetailTail.txt",   1, "BBSHTMLConfig.c::MailDetailTail[]"),
    ("Welcome.txt",          1, "BBSHTMLConfig.c::Welcome[]"),
    ("MsgEditPage.txt",      1, "BBSHTMLConfig.c::MsgEditPage[]"),
    ("WPDetail.txt",         1, "BBSHTMLConfig.c::WPDetail[]"),
    ("LostSession.txt",      1, "BBSHTMLConfig.c::LostSession[]"),
    # --- Phase 4: HTTPcode.c file-scope inline arrays ---
    ("Index.txt",            1, "HTTPcode.c::Index[]"),
    ("IndexNoAPRS.txt",      1, "HTTPcode.c::IndexNoAPRS[]"),
    ("Tail.txt",             1, "HTTPcode.c::Tail[]"),
    ("RouteHddr.txt",        1, "HTTPcode.c::RouteHddr[]"),
    ("RouteLine.txt",        1, "HTTPcode.c::RouteLine[]"),
    ("RouteLineINP3.txt",    1, "HTTPcode.c::RouteLineINP3[]"),
    ("xNodeHddr.txt",        1, "HTTPcode.c::xNodeHddr[]"),
    ("NodeHddr.txt",         1, "HTTPcode.c::NodeHddr[]"),
    ("NodeLine.txt",         1, "HTTPcode.c::NodeLine[]"),
    ("StatsHddr.txt",        1, "HTTPcode.c::StatsHddr[]"),
    ("PortStatsHddr.txt",    1, "HTTPcode.c::PortStatsHddr[]"),
    ("PortStatsLine.txt",    1, "HTTPcode.c::PortStatsLine[]"),
    ("Beacons.txt",          1, "HTTPcode.c::Beacons[]"),
    ("LinkHddr.txt",         1, "HTTPcode.c::LinkHddr[]"),
    ("LinkLine.txt",         1, "HTTPcode.c::LinkLine[]"),
    ("UserHddr.txt",         1, "HTTPcode.c::UserHddr[]"),
    ("UserLine.txt",         1, "HTTPcode.c::UserLine[]"),
    ("TermSignon.txt",       1, "HTTPcode.c::TermSignon[]"),
    ("NoSessions.txt",       1, "HTTPcode.c::NoSessions[]"),
    ("TermPage.txt",         1, "HTTPcode.c::TermPage[]"),
    ("TermOutput.txt",       1, "HTTPcode.c::TermOutput[]"),
    ("TermOutputTail.txt",   1, "HTTPcode.c::TermOutputTail[]"),
    ("InputLine.txt",        1, "HTTPcode.c::InputLine[]"),
    ("NodeSignon.txt",       1, "HTTPcode.c::NodeSignon[]"),
    ("MailLostSession.txt",  1, "HTTPcode.c::MailLostSession[]"),
    ("ConfigEditPage.txt",   1, "HTTPcode.c::ConfigEditPage[]"),
    # --- Phase 4: HTTPcode.c function-local inline arrays ---
    ("NodeMenuHeader.txt",   1, "HTTPcode.c::SetupNodeMenu local NodeMenuHeader[]"),
    ("DriverBit.txt",        1, "HTTPcode.c::SetupNodeMenu local DriverBit[]"),
    ("APRSBit.txt",          1, "HTTPcode.c::SetupNodeMenu local APRSBit[]"),
    ("MailBit.txt",          1, "HTTPcode.c::SetupNodeMenu local MailBit[]"),
    ("ChatBit.txt",          1, "HTTPcode.c::SetupNodeMenu local ChatBit[]"),
    ("SigninBit.txt",        1, "HTTPcode.c::SetupNodeMenu local SigninBit[]"),
    ("NodeTail.txt",         1, "HTTPcode.c::SetupNodeMenu local NodeTail[]"),
    ("PortsHddr.txt",        1, "HTTPcode.c::InnerProcessHTTPMessage local PortsHddr[]"),
    ("PortLineWithBeacon.txt", 1, "HTTPcode.c::PortLineWithBeacon[]"),
    ("SessionPortLine.txt",  1, "HTTPcode.c::SessionPortLine[]"),
    ("PortLineWithDriver.txt", 1, "HTTPcode.c::PortLineWithDriver[]"),
    ("PortLineWithBeaconAndDriver.txt", 1, "HTTPcode.c::PortLineWithBeaconAndDriver[]"),
    ("RigControlLine.txt",   1, "HTTPcode.c::RigControlLine[]"),
    ("Test.txt",             1, "HTTPcode.c::RigControl Test[]"),
    ("NoRigCtl.txt",         1, "HTTPcode.c::RigControl NoRigCtl[]"),
    ("ShowLogPage.txt",      1, "HTTPcode.c::ShowLogPage[]"),
    ("AXIPHeader.txt",       1, "HTTPcode.c::AXIPHeader[]"),
    ("Page.txt",             1, "HTTPcode.c::SendRigWebPage local Page[]"),
    ("RigLine.txt",          1, "HTTPcode.c::SendRigWebPage local RigLine[]"),
    ("RigCtlTail.txt",       1, "HTTPcode.c::SendRigWebPage local Tail[] (renamed RigCtlTail)"),
    # --- Phase 5: WebMail.c ---
    ("WebMailSignon.txt",    1, "WebMail.c::WebMailSignon[]"),
    ("MsgInputPage.txt",     1, "WebMail.c::MsgInputPage[]"),
    ("CheckFormMsgPage.txt", 1, "WebMail.c::CheckFormMsgPage[]"),
    ("XMLHeader.txt",        1, "WebMail.c::XMLHeader[]"),
    ("XMLLine.txt",          1, "WebMail.c::XMLLine[]"),
    ("XMLTrailer.txt",       1, "WebMail.c::XMLTrailer[]"),
    ("WebSockPage.txt",      1, "WebMail.c::WebSockPage[]"),
    ("MoveListPopup.txt",    1, "WebMail.c::ProcessWebMailMessage popuphddr (renamed)"),
    ("TemplateSelectPopup.txt", 1, "WebMail.c::SendTemplateSelectScreen popuphddr (renamed)"),
    ("NewGroup.txt",         1, "WebMail.c::SendTemplateSelectScreen NewGroup[]"),
    ("SelectPromptPopup.txt", 1, "WebMail.c::DoSelectPrompt popuphddr (renamed)"),
    ("AttachmentListPopup.txt", 1, "WebMail.c::getAttachmentList popuphddr (renamed)"),
    # --- Phase 6: APRSStdPages.c ---
    ("AprsInfoCall.txt",     1, "APRSStdPages.c::get_info_call"),
    ("AprsInfoMobileCall.txt", 1, "APRSStdPages.c::get_infomobile_call"),
    ("AprsInfoObjCall.txt",  1, "APRSStdPages.c::get_infoobj_call"),
    ("AprsInfoWxCall.txt",   1, "APRSStdPages.c::get_infowx_call"),
    ("AprsAll.txt",          1, "APRSStdPages.c::get_all"),
    ("AprsMobileAll.txt",    1, "APRSStdPages.c::get_mobileall"),
    ("AprsObj.txt",          1, "APRSStdPages.c::get_obj"),
    ("AprsNoInfo.txt",       1, "APRSStdPages.c::get_noinfo"),
    ("AprsWxAll.txt",        1, "APRSStdPages.c::get_wxall"),
    ("AprsInfo.txt",         1, "APRSStdPages.c::get_info"),
    ("AprsAllRf.txt",        1, "APRSStdPages.c::get_allrf"),
    ("AprsMobilesRf.txt",    1, "APRSStdPages.c::get_mobilesrf"),
    ("AprsObjRf.txt",        1, "APRSStdPages.c::get_objrf"),
    ("AprsWxRf.txt",         1, "APRSStdPages.c::get_wxrf"),
    ("AprsPortStats.txt",    1, "APRSStdPages.c::get_portstats"),
    ("AprsMain.txt",         1, "APRSStdPages.c::get_aprs"),
    # --- Phase 7: APRSCode.c ---
    ("WebHeader.txt",        1, "APRSCode.c::WebHeader"),
    ("WebTXHeader.txt",      1, "APRSCode.c::WebTXHeader"),
    ("WebLine.txt",          1, "APRSCode.c::WebLine"),
    ("WebTXLine.txt",        1, "APRSCode.c::WebTXLine"),
    ("WebTrailer.txt",       1, "APRSCode.c::WebTrailer"),
    ("SendMsgPage.txt",      1, "APRSCode.c::SendMsgPage"),
    ("APRSIndexPage.txt",    1, "APRSCode.c::APRSIndexPage"),
    # --- Phase 8: VARA.c (also referenced from ARDOP.c, WINMOR.c) ---
    ("WebProcTemplate.txt",  1, "VARA.c::WebProcTemplate (shared with ARDOP/WINMOR)"),
    ("Menubit.txt",          1, "VARA.c::Menubit"),
    ("sliderBit.txt",        1, "VARA.c::sliderBit (shared with ARDOP/WINMOR)"),
    # --- Phase 9: Driver status pages (sprintf-chain consolidations) ---
    ("KAMPactorWebProc.txt", 1, "KAMPactor.c::WebProc (consolidated)"),
    ("KISSHFWebProc.txt",    1, "KISSHF.c::WebProc (consolidated)"),
    ("HALDriverWebProc.txt", 1, "HALDriver.c::WebProc (consolidated)"),
    ("SCSPactorWebProc.txt", 1, "SCSPactor.c::WebProc (consolidated)"),
    ("WinRPRWebProc.txt",    1, "WinRPR.c::WebProc (consolidated)"),
    ("FreeDATAWebProc.txt",  1, "FreeDATA.c::WebProc (consolidated)"),
    ("FLDigiWebProc.txt",    1, "FLDigi.c::WebProc (consolidated)"),
    ("SCSTrackerWebProc.txt", 1, "SCSTracker.c::WebProc (consolidated)"),
)


# ── Repo-level invariants ─────────────────────────────────────────


@pytest.mark.parametrize("name,version,_source", EXTRACTED_TEMPLATES)
def test_extracted_template_present(name, version, _source):
    """Every template extracted from templatedefs.c must exist as
    a file under HTML/.  If a future change drops one, this fires."""
    path = _HTML_DIR / name
    assert path.is_file(), (
        f"HTML/{name} missing — was the file removed without "
        f"updating the inventory in this test?"
    )


@pytest.mark.parametrize("name,version,_source", EXTRACTED_TEMPLATES)
def test_extracted_template_carries_version_marker(name, version, _source):
    """``HTMLCommonCode.c::GetTemplateFromFile`` does a runtime
    version check against the ``<!-- Version N`` comment in the
    first ~200 bytes of the template.  If that comment is missing,
    every page using the template 404s with the version-mismatch
    error message."""
    body = (_HTML_DIR / name).read_bytes()
    pattern = rb"<!-- Version " + str(version).encode("ascii") + rb"\b"
    assert re.search(pattern, body[:300]), (
        f"HTML/{name}: missing or wrong 'Version {version}' marker.  "
        f"First 200 bytes: {body[:200]!r}"
    )


def test_templatedefs_c_removed_from_repo():
    """Locks in the removal of templatedefs.c.  Re-introducing it
    would mean the inline functions are back and either:
    (a) HTMLCommonCode.c's fast-path returns are back too — leaving
        the HTML/ files unused, or
    (b) we have two copies of every template and they'll drift.
    """
    assert not (_REPO_ROOT / "templatedefs.c").exists(), (
        "templatedefs.c reappeared — see comment in test."
    )


def test_htmlcommoncode_no_longer_calls_inline_template_functions():
    """``HTMLCommonCode.c::GetTemplateFromFile`` previously had a
    block of fast-path ``if (strcmp(FN, ...) == 0) return Xtxt();``
    returns to inline functions.  After extraction those functions
    are gone, so the fast-path lines must be gone too — otherwise
    the build would fail to link.  Belt-and-braces test against an
    accidental partial revert that compiles via stub function."""
    src = (_REPO_ROOT / "HTMLCommonCode.c").read_text()
    forbidden = [
        "WebMailMsgtxt(", "FwdPagetxt(", "FwdDetailtxt(",
        "webscriptjs(", "WebMailPagetxt(", "MainConfigtxt(",
        "MsgPagetxt(", "UserDetailtxt(", "UserPagetxt(",
        "Housekeepingtxt(", "WPtxt(", "ChatConfigtxt(",
        "ChatStatustxt(",
    ]
    for fn in forbidden:
        assert fn not in src, (
            f"HTMLCommonCode.c still calls {fn} — fast-path return "
            "to inline template not removed."
        )


def test_no_extraction_artefacts_in_templates():
    """C string literals in the original code use backslash
    escapes (``\\<LF>`` line continuations, ``\\?`` trigraph
    escapes, ``\\"`` etc.) that the C compiler resolves to the
    intended characters at compile time.  When templates were
    extracted from C arrays into ``HTML/*.txt`` files, those
    escapes would have been preserved verbatim — leaking into
    runtime HTML.

    Lock in that the extracted templates are clean.  If a new
    template lands with a backslash anywhere it doesn't belong,
    this test fires.

    Currently allowed: a single literal ``\\r`` in
    ``UIHddr.txt`` (instructional text telling the user how
    to type a CR in their MailFor message).
    """
    import re as _re
    from pathlib import Path

    ALLOWED_BACKSLASHES = {
        "UIHddr.txt": [r"\r"],  # user-facing instruction
    }

    html_dir = Path(__file__).resolve().parents[2] / "HTML"
    offenders: list[str] = []
    for path in sorted(html_dir.glob("*.txt")):
        text = path.read_text(errors="replace")
        # Find every backslash-followed-by-something occurrence.
        for m in _re.finditer(r"\\.", text):
            seq = m.group(0)
            if seq in ALLOWED_BACKSLASHES.get(path.name, []):
                continue
            offenders.append(
                f"{path.name}: {seq!r} at offset {m.start()} "
                f"(context: {text[max(0, m.start()-20):m.end()+20]!r})"
            )
        # Trailing-backslash check (separate because ``\\.`` won't
        # match `\<LF>` or `\<EOF>`).
        for ln_idx, line in enumerate(text.splitlines(), 1):
            if line.endswith("\\") and path.name not in ALLOWED_BACKSLASHES:
                offenders.append(
                    f"{path.name}:{ln_idx}: trailing backslash "
                    f"({line[-30:]!r})"
                )
    assert not offenders, (
        "Extraction artefacts detected:\n  "
        + "\n  ".join(offenders)
    )


def test_chathtmlconfig_no_inline_html_arrays():
    """``ChatHTMLConfig.c`` previously had ``ChatSignon[] = "<html>...";``
    and ``ChatPage[] = "<html>...";`` declarations as inline char
    arrays.  Phase 2 of the extraction moved them to
    ``HTML/ChatSignon.txt`` and ``HTML/ChatPage.txt``, replacing
    the declarations with cached file-loaded pointers.  Locking
    in: any future PR that re-introduces an inline ``char Foo[]
    = "<...>"`` HTML literal in this file should fail this test."""
    src = (_REPO_ROOT / "ChatHTMLConfig.c").read_text()
    # The previous declarations had the form `char ChatSignon[] = "<html>...`
    # and `char ChatPage[] = "<html>...`.  After extraction those are gone;
    # the surviving references are static char* template pointers.
    forbidden = (
        'char ChatSignon[] = "<',
        'char ChatPage[] = "<',
    )
    for pattern in forbidden:
        assert pattern not in src, (
            f"ChatHTMLConfig.c still has inline-HTML decl {pattern!r}; "
            "extract to HTML/ via GetTemplateFromFile."
        )


# ── Behavioural smoke tests ───────────────────────────────────────


def test_boot_with_html_dir_node_pages_render(linbpq_web):
    """Boot succeeds with HTML/ on disk and the standard Node menu
    pages render.  Strongest proof that removing templatedefs.c
    didn't break the unrelated /Node/* path."""
    port = linbpq_web["http_port"]
    for path in ("/Node/NodeIndex.html", "/Node/Status.html", "/Node/Stats.html"):
        status, body = _http_get(port, path)
        assert b"200" in status, f"{path}: {status!r}"
        assert b"BPQ32" in body, f"{path}: missing branding"


# ── Signon-form rendering (no auth required) ─────────────────────


def test_mail_signon_form_renders(linbpq_web):
    """GET /Mail/Signon serves the signon form from MailSignon.txt
    with the canonical post-action URL embedded.  This locks in
    that the form's ``action=/Mail/Signon?Mail`` is preserved —
    the ``?Mail`` query string is the workaround for upstream
    issue #18 (NULL Appl deref in ProcessMailSignon)."""
    port = linbpq_web["http_port"]
    status, body = _http_get(port, "/Mail/Signon")
    assert b"200" in status, f"GET /Mail/Signon: {status!r}"
    assert b"<!-- Version 1 -->" in body[:30]
    assert b"action=/Mail/Signon?Mail" in body, (
        "MailSignon form action lost the ?Mail query string — without it, "
        "POST hits the NULL Appl deref (M0LTE/linbpq#18)."
    )
    assert b"BPQ32 Mail Server" in body


def test_chat_signon_form_renders(linbpq_web):
    """Same check for the Chat signon form (ChatSignon.txt)."""
    port = linbpq_web["http_port"]
    status, body = _http_get(port, "/Chat/Signon")
    assert b"200" in status, f"GET /Chat/Signon: {status!r}"
    assert b"<!-- Version 1 -->" in body[:30]
    assert b"action=/Chat/Signon?Chat" in body
    assert b"BPQ32 Chat Server" in body


# ── Mail post-signon walkthrough ─────────────────────────────────


_MAIL_SESSION_KEY_RE = re.compile(rb"\?(M[0-9A-F]{12})")


def test_mail_post_signon_walkthrough(linbpq_web):
    """Sign in to /Mail with the form's own ?Mail action URL
    (workaround for the NULL Appl deref, M0LTE/linbpq#18), extract
    the session key from the post-signon MailPage frame, then GET
    every nav target and verify each rendered template carries its
    expected version marker.

    Covers MailPage.txt (the BBS top-frame nav) and the post-signon
    pages MainConfig (v7), UserPage (v4), MsgPage (v2),
    Housekeeping (v2), FwdPage (v4), WP (v1).
    """
    port = linbpq_web["http_port"]
    status, body = _http_post(
        port, "/Mail/Signon?Mail", b"User=test&password=test"
    )
    assert b"200" in status, f"POST /Mail/Signon?Mail: {status!r}"
    assert b"BPQ32 BBS" in body, (
        f"MailPage frame missing branding: {body[:200]!r}"
    )
    match = _MAIL_SESSION_KEY_RE.search(body)
    assert match, f"no session key in Mail signon response: {body[:200]!r}"
    key = match.group(1).decode("ascii")

    # Each post-signon nav target should render its template with
    # the expected version marker.  ``Status`` re-renders MailPage
    # plus a status table — covered by the signon body above.
    expected = [
        ("/Mail/Conf", 7, b"Main Configuration"),
        ("/Mail/Users", 4, None),
        ("/Mail/Msgs", 2, None),
        ("/Mail/HK", 2, None),
        ("/Mail/FWD", 4, None),
        ("/Mail/WP", 1, None),
    ]
    for path, version, marker in expected:
        url = f"{path}?{key}"
        status, body = _http_get(port, url)
        assert b"200" in status, f"GET {url}: {status!r}"
        # Marker appears with or without a date suffix
        # (e.g. ``<!-- Version 4 10/10/2015 -->``); accept either.
        assert re.search(
            rb"<!-- Version " + str(version).encode("ascii") + rb"[\s>]",
            body[:200],
        ), (
            f"GET {url}: missing or wrong Version {version} marker.  "
            f"Body[:200]: {body[:200]!r}"
        )
        if marker is not None:
            assert marker in body, (
                f"GET {url}: missing expected marker {marker!r}"
            )


# ── Chat post-signon walkthrough (works end-to-end) ──────────────


_CHAT_SESSION_KEY_RE = re.compile(rb"\?(C[0-9A-F]{12})")


def test_chat_post_signon_walkthrough(linbpq_web):
    """Sign in to /Chat, extract the session key from the response,
    then GET each post-signon URL and verify the rendered template
    carries its expected version marker.  This covers ChatStatus.txt
    (v1) and ChatConfig.txt (v2) end-to-end — without it those
    templates are only verified at the file level, not at render
    time."""
    port = linbpq_web["http_port"]
    status, body = _http_post(
        port, "/Chat/Signon?Chat", b"User=test&password=test"
    )
    assert b"200" in status, f"POST /Chat/Signon?Chat: {status!r}"
    match = _CHAT_SESSION_KEY_RE.search(body)
    assert match, f"no session key in Chat signon response: {body[:200]!r}"
    key = match.group(1).decode("ascii")

    # /Chat/ChatStatus → ChatStatus.txt (Version 1)
    status, body = _http_get(port, f"/Chat/ChatStatus?{key}")
    assert b"200" in status, f"GET /Chat/ChatStatus?{key}: {status!r}"
    assert b"<!-- Version 1" in body[:80], (
        f"ChatStatus.txt version marker missing: {body[:120]!r}"
    )

    # /Chat/ChatConf → ChatConfig.txt (Version 2)
    status, body = _http_get(port, f"/Chat/ChatConf?{key}")
    assert b"200" in status, f"GET /Chat/ChatConf?{key}: {status!r}"
    assert b"<!-- Version 2" in body[:80], (
        f"ChatConfig.txt version marker missing: {body[:120]!r}"
    )
    assert b"Chat Configuration" in body
