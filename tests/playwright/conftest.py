"""Playwright UI test scaffolding for linbpq's HTTP server.

These tests boot a real linbpq.bin in a per-test temp directory,
hit the HTTP server, and verify pages load.  The purpose is to
lock in the user-visible behaviour of every HTML page so we can
extract the embedded HTML out of the C source into template files
without regressions.

Coverage strategy:

- Each ``GET /Mail/*`` and ``/Chat/*`` URL exercised at least once.
- Form submissions round-tripped where possible — POST data,
  reload page, verify the submitted value persists.
- Where a page renders dynamic data (status counters, tables of
  users / messages / partners), we assert structural elements
  (table headers, form fields, button labels) rather than the
  literal text — so passing the test means the page works, not
  that the bytes are byte-identical to the previous build.

Fixtures provided:

- ``linbpq_web``: linbpq with mail + chat enabled, no APRS.
- ``linbpq_web_with_aprs``: same plus an APRS port + APRSCALL,
  so /APRS/* pages render non-trivial content.
- ``mail_session`` / ``chat_session``: signs in as the SYSOP test
  user and returns a dict containing the http port and the
  session key, ready for follow-up ``http_get`` calls against
  ``/Mail/...?<key>`` etc.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

# Reuse port-picking helper from the integration suite.
_INTEG_DIR = Path(__file__).resolve().parents[1] / "integration"
sys.path.insert(0, str(_INTEG_DIR))
from helpers.linbpq_instance import pick_free_port  # type: ignore  # noqa: E402

from web_helpers import (  # noqa: E402
    add_bbs_user,
    chat_signon,
    mail_signon,
    send_bbs_message_via_telnet,
)


LINBPQ_BIN = os.environ.get("LINBPQ_BIN", "linbpq.bin")


_BASE_CFG = """\
SIMPLE=1
NODECALL=N0CALL
NODEALIAS=TEST
LOCATOR=NONE
APPLICATIONS=BBS,CHAT
BBSCALL=N0CALL-1
BBSALIAS=BBS
APPL1CALL=N0CALL-1
APPL1ALIAS=BBS
APPL2CALL=N0CALL-2
APPL2ALIAS=CHT

PORT
 ID=Telnet
 DRIVER=Telnet
 CONFIG
 TCPPORT={telnet_port}
 HTTPPORT={http_port}
 MAXSESSIONS=10
 USER=test,test,N0CALL,,SYSOP
ENDPORT
"""

# APRS variant: extra PORT block + APRS keywords up top.  Keeps
# the same telnet+http listeners so existing helpers keep working.
_APRS_CFG = """\
SIMPLE=1
NODECALL=N0CALL
NODEALIAS=TEST
LOCATOR=IO91WM
APPLICATIONS=BBS,CHAT
BBSCALL=N0CALL-1
BBSALIAS=BBS
APPL1CALL=N0CALL-1
APPL1ALIAS=BBS
APPL2CALL=N0CALL-2
APPL2ALIAS=CHT
APRSPORT=2
APRSCALL=N0CALL-9

PORT
 ID=Telnet
 DRIVER=Telnet
 CONFIG
 TCPPORT={telnet_port}
 HTTPPORT={http_port}
 MAXSESSIONS=10
 USER=test,test,N0CALL,,SYSOP
ENDPORT

PORT
 ID=APRS-loop
 DRIVER=AXIP
 CONFIG
 PROTOCOL=AXIP
 TXPORT=18999
 ENDPORT
"""


_REPO_ROOT = Path(__file__).resolve().parents[2]
_HTML_DIR = _REPO_ROOT / "HTML"

_CHATCONFIG = (
    'Chat :\n{\n'
    '  ApplNum = 2;\n'
    '  MaxStreams = 10;\n'
    '  reportChatEvents = 0;\n'
    '  chatPaclen = 236;\n'
    '  OtherChatNodes = "";\n'
    '  ChatWelcomeMsg = "Welcome to the test chat node!";\n'
    '  MapPosition = "";\n'
    '  MapPopup = "";\n'
    '  PopupMode = 0;\n'
    '};\n'
)


def _setup_workdir(tmp_path: Path, cfg: str) -> None:
    (tmp_path / "bpq32.cfg").write_text(cfg)
    (tmp_path / "chatconfig.cfg").write_text(_CHATCONFIG)
    if _HTML_DIR.is_dir():
        target = tmp_path / "HTML"
        target.mkdir(exist_ok=True)
        # Copy files at the top level + recurse subdirs (e.g.
        # samples/) so SendMessageFile can resolve URLs like
        # /samples/index.html in the test workdir.
        for src in _HTML_DIR.iterdir():
            if src.is_file():
                (target / src.name).write_bytes(src.read_bytes())
            elif src.is_dir():
                subdir = target / src.name
                subdir.mkdir(exist_ok=True)
                for subfile in src.iterdir():
                    if subfile.is_file():
                        (subdir / subfile.name).write_bytes(subfile.read_bytes())


def _wait_for_http(http_port: int, proc: subprocess.Popen, log_path: Path) -> None:
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", http_port), timeout=0.5):
                return
        except OSError:
            if proc.poll() is not None:
                raise RuntimeError(
                    f"linbpq exited rc={proc.returncode}; see {log_path}"
                )
            time.sleep(0.1)
    proc.terminate()
    raise TimeoutError(
        f"linbpq HTTP port {http_port} didn't open within 10s"
    )


def _wait_for_bbs_ready(http_port: int, log_path: Path) -> None:
    """The HTTP port opens before the BBS subsystem finishes
    starting up.  /WebMail returns the WebMailPage (Version 6)
    once the BBS is registered; until then it serves a fallback
    that looks like the WebMailSignon page (Version 1).  Poll the
    log for "Mail Started" and verify /WebMail renders the right
    template before letting tests run.
    """
    import urllib.request

    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{http_port}/WebMail",
                headers={"Accept-Encoding": "deflate"},
            )
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                body = resp.read()
                if resp.headers.get("Content-Encoding", "").lower() == "deflate":
                    import zlib as _zlib
                    body = _zlib.decompress(body)
                if b"<!-- Version 6" in body[:300]:
                    return
        except (OSError, ValueError):
            pass
        time.sleep(0.2)
    raise TimeoutError(
        f"BBS subsystem didn't reach ready state within 10s; see {log_path}"
    )


def _start_linbpq(tmp_path: Path, cfg: str) -> dict:
    """Boot linbpq with the given config + return a metadata dict.

    Caller is responsible for terminating ``proc`` at teardown
    (via the fixture's ``finally`` block).
    """
    telnet_port = pick_free_port()
    http_port = pick_free_port()
    cfg_text = cfg.format(telnet_port=telnet_port, http_port=http_port)
    _setup_workdir(tmp_path, cfg_text)

    log = (tmp_path / "linbpq.stdout.log").open("wb")
    proc = subprocess.Popen(
        [LINBPQ_BIN, "mail", "chat"],
        cwd=tmp_path,
        stdout=log,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
    )
    try:
        _wait_for_http(http_port, proc, tmp_path / "linbpq.stdout.log")
        _wait_for_bbs_ready(http_port, tmp_path / "linbpq.stdout.log")
    except Exception:
        log.close()
        raise
    return {
        "base_url": f"http://127.0.0.1:{http_port}",
        "telnet_port": telnet_port,
        "http_port": http_port,
        "work_dir": tmp_path,
        "proc": proc,
        "log": log,
    }


def _shutdown_linbpq(meta: dict) -> None:
    proc = meta["proc"]
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
    meta["log"].close()


@pytest.fixture
def linbpq_web(tmp_path: Path):
    """Boot a linbpq with mail + chat enabled.  Yields a dict
    with ``base_url``, ``telnet_port``, ``http_port``, ``work_dir``."""
    meta = _start_linbpq(tmp_path, _BASE_CFG)
    try:
        yield {k: v for k, v in meta.items() if k not in ("proc", "log")}
    finally:
        _shutdown_linbpq(meta)


@pytest.fixture
def linbpq_web_with_aprs(tmp_path: Path):
    """Boot a linbpq with an APRS port + APRSCALL enabled, in
    addition to mail + chat.  Use this for /APRS/* tests where the
    pages render based on APRS port state.
    """
    meta = _start_linbpq(tmp_path, _APRS_CFG)
    try:
        yield {k: v for k, v in meta.items() if k not in ("proc", "log")}
    finally:
        _shutdown_linbpq(meta)


@pytest.fixture
def mail_session(linbpq_web):
    """Sign in to /Mail and yield ``{port, key, base}`` ready for
    ``http_get(port, f"/Mail/Conf?{key}")`` etc."""
    port = linbpq_web["http_port"]
    key = mail_signon(port)
    return {"port": port, "key": key, "base": linbpq_web["base_url"]}


@pytest.fixture
def chat_session(linbpq_web):
    """Sign in to /Chat and yield ``{port, key, base}``."""
    port = linbpq_web["http_port"]
    key = chat_signon(port)
    return {"port": port, "key": key, "base": linbpq_web["base_url"]}


# ── Seeded fixture: BBS pre-populated with users + messages ──────


SEEDED_USERS = ["M0XYZ", "M0ABC", "G8BPQ"]

SEEDED_MESSAGES = [
    {
        "to": "ALL",
        "subject": "Test bulletin one",
        "body": ["This is the body of test bulletin number one.", "73 de N0CALL"],
    },
    {
        "to": "M0XYZ",
        "subject": "Personal test message",
        "body": ["Hello M0XYZ, this is a test.", "Please ignore."],
    },
    {
        "to": "ALL",
        "subject": "Second bulletin",
        "body": ["Another bulletin for the test corpus."],
    },
]


@pytest.fixture
def linbpq_web_seeded(linbpq_web):
    """Boot linbpq + seed the BBS with non-empty state.

    Adds 3 BBS users via /Mail/UserSave (Add=<call>) and attempts
    to send a few messages via the telnet command line.

    Yields a dict including ``users``: the list of seeded
    callsigns, and ``messages``: the list of message specs that
    were attempted.  Tests can use these to assert the rendered
    list pages contain real data, not just empty-state shells.

    Telnet-driven message seeding is best-effort — if the BBS
    prompt sequence doesn't match the expected pattern, the
    helper times out silently rather than failing the test.
    """
    port = linbpq_web["http_port"]
    telnet_port = linbpq_web["telnet_port"]
    key = mail_signon(port)

    for call in SEEDED_USERS:
        add_bbs_user(port, key, call)

    seeded_msgs = []
    for spec in SEEDED_MESSAGES:
        try:
            send_bbs_message_via_telnet(
                telnet_port,
                "test",
                "test",
                to=spec["to"],
                subject=spec["subject"],
                body_lines=spec["body"],
            )
            seeded_msgs.append(spec)
        except (RuntimeError, OSError):
            # Best-effort — telnet automation timing is fragile.
            pass

    return {
        **linbpq_web,
        "key": key,
        "users": SEEDED_USERS,
        "messages": seeded_msgs,
    }


# ── Browser-tier fixtures (pytest-playwright) ─────────────────────


@pytest.fixture
def browser_context_args(browser_context_args, linbpq_web):
    """Override pytest-playwright's default context args so the
    Playwright ``page`` fixture is automatically pointed at the
    per-test linbpq HTTP base URL.
    """
    return {**browser_context_args, "base_url": linbpq_web["base_url"]}


@pytest.fixture
def authed_page(page, linbpq_web):
    """A Playwright ``Page`` already past the BBS signon flow.
    Performs a one-shot POST against /Mail/Signon?Mail to
    establish the cookie/session, then navigates to /Node/.
    Tests can drive ``page`` from there without each test having
    to repeat the auth dance.
    """
    page.goto("/Mail/Signon")
    page.fill('input[name="user"]', "test")
    page.fill('input[name="password"]', "test")
    page.click('input[type="submit"][value="Submit"]')
    return page


class _ConsoleErrorCapture:
    """Helper: collect JS errors / console-error messages from a
    Playwright ``Page`` so tests can assert "no JS errors fired
    while we did X".  Use it as a context manager:

        with capture_js_errors(page) as errors:
            page.goto(...)
            page.click(...)
        assert not errors, f"JS errors during interaction: {errors}"
    """

    def __init__(self, page):
        self.page = page
        self.errors: list[str] = []
        self._on_pageerror = lambda exc: self.errors.append(f"pageerror: {exc}")
        self._on_console = lambda msg: (
            self.errors.append(f"console.error: {msg.text}")
            if msg.type == "error"
            else None
        )

    def __enter__(self):
        self.page.on("pageerror", self._on_pageerror)
        self.page.on("console", self._on_console)
        return self.errors

    def __exit__(self, exc_type, exc_val, exc_tb):
        # pytest-playwright cleans the page up; no need to detach
        # listeners (the page itself is per-test).
        return False


@pytest.fixture
def capture_js_errors():
    """Yield a callable that, given a Page, returns a context
    manager collecting JS errors during the with-block.  See
    ``_ConsoleErrorCapture`` docstring for usage."""
    return _ConsoleErrorCapture
