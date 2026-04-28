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

The fixture in this file boots a single linbpq instance per test
with mail + chat enabled and yields its HTTP base URL.
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


LINBPQ_BIN = os.environ.get("LINBPQ_BIN", "linbpq.bin")


_CFG_TEMPLATE = """\
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


_REPO_ROOT = Path(__file__).resolve().parents[2]
_HTML_DIR = _REPO_ROOT / "HTML"


@pytest.fixture
def linbpq_web(tmp_path: Path):
    """Boot a linbpq with mail + chat enabled and yield a dict of
    URL + port info.  Copies the repo's ``HTML/`` directory into
    the work dir so file-loaded templates resolve correctly
    (BPQDirectory == cwd at runtime, see HTMLCommonCode.c).
    Tears down at end of test."""
    telnet_port = pick_free_port()
    http_port = pick_free_port()
    cfg = _CFG_TEMPLATE.format(telnet_port=telnet_port, http_port=http_port)
    (tmp_path / "bpq32.cfg").write_text(cfg)
    # Copy HTML/ templates into the work dir so GetTemplateFromFile
    # resolves them.  Without this the BBS / Chat / WebMail web-UI
    # endpoints return "File is missing" stubs.
    if _HTML_DIR.is_dir():
        target = tmp_path / "HTML"
        target.mkdir(exist_ok=True)
        for src in _HTML_DIR.iterdir():
            if src.is_file():
                (target / src.name).write_bytes(src.read_bytes())
    # Pre-seed chatconfig.cfg with the libconfig format BPQChat
    # expects (Chat:{...};) so chat starts cleanly.  ApplNum must
    # match APPL2 in bpq32.cfg.
    (tmp_path / "chatconfig.cfg").write_text(
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
    log = (tmp_path / "linbpq.stdout.log").open("wb")
    proc = subprocess.Popen(
        [LINBPQ_BIN, "mail", "chat"],
        cwd=tmp_path,
        stdout=log,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
    )
    # Wait for HTTP listener to come up.
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", http_port), timeout=0.5):
                break
        except OSError:
            if proc.poll() is not None:
                log.close()
                raise RuntimeError(
                    f"linbpq exited rc={proc.returncode}; see {tmp_path}/linbpq.stdout.log"
                )
            time.sleep(0.1)
    else:
        proc.terminate()
        log.close()
        raise TimeoutError(
            f"linbpq HTTP port {http_port} didn't open within 10s"
        )
    # Give chat a moment to register.
    time.sleep(0.5)
    try:
        yield {
            "base_url": f"http://127.0.0.1:{http_port}",
            "telnet_port": telnet_port,
            "http_port": http_port,
            "work_dir": tmp_path,
        }
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        log.close()
