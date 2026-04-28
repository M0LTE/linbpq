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

from web_helpers import mail_signon, chat_signon  # noqa: E402


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
        for src in _HTML_DIR.iterdir():
            if src.is_file():
                (target / src.name).write_bytes(src.read_bytes())


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
    except Exception:
        log.close()
        raise
    # Give the subsystem threads a moment to register.
    time.sleep(0.5)
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
