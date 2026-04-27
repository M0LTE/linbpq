"""Telnet driver options (the ``CONFIG`` block keywords).

Custom prompts and the block-level ``CTEXT=`` keyword are visible
on the wire — easy to test directly from a telnet probe.

``LOCALNET=`` (sysop-trust whitelist by source IP) and
``SECURETELNET`` / ``DisconnectOnClose`` are tested only at the
"accepted-cleanly, daemon still works" level — driving the
behaviour they control needs source-IP spoofing or non-trivial
client lifecycle scripting.
"""

from __future__ import annotations

import socket
import time
from pathlib import Path
from string import Template

from helpers.linbpq_instance import LinbpqInstance


def _read_until(sock: socket.socket, marker: bytes, timeout: float = 3.0) -> bytes:
    deadline = time.monotonic() + timeout
    buf = b""
    while marker not in buf and time.monotonic() < deadline:
        sock.settimeout(0.4)
        try:
            chunk = sock.recv(4096)
        except (TimeoutError, socket.timeout):
            continue
        if not chunk:
            break
        buf += chunk
    return buf


def _telnet_cfg_with(extras: str) -> Template:
    return Template(
        f"""\
SIMPLE=1
NODECALL=N0CALL
NODEALIAS=TEST
LOCATOR=NONE

PORT
 ID=Telnet
 DRIVER=Telnet
 CONFIG
 TCPPORT=$telnet_port
 HTTPPORT=$http_port
{extras}
 MAXSESSIONS=10
 USER=test,test,N0CALL,,SYSOP
ENDPORT
"""
    )


def test_loginprompt_custom_string_appears(tmp_path: Path):
    """``LOGINPROMPT=…`` replaces the default ``user:`` prompt."""
    cfg = _telnet_cfg_with(" LOGINPROMPT=Login-Now:")
    with LinbpqInstance(tmp_path, config_template=cfg) as linbpq:
        with socket.create_connection(("127.0.0.1", linbpq.telnet_port), timeout=3) as sock:
            data = _read_until(sock, b"Login-Now:", timeout=3)
    assert b"Login-Now:" in data, f"custom login prompt missing: {data!r}"


def test_passwordprompt_custom_string_appears(tmp_path: Path):
    """``PASSWORDPROMPT=…`` replaces the default ``password:``."""
    cfg = _telnet_cfg_with(" PASSWORDPROMPT=Pass-Now:")
    with LinbpqInstance(tmp_path, config_template=cfg) as linbpq:
        with socket.create_connection(("127.0.0.1", linbpq.telnet_port), timeout=3) as sock:
            _read_until(sock, b"user:", timeout=3)
            sock.sendall(b"test\r")
            data = _read_until(sock, b"Pass-Now:", timeout=3)
    assert b"Pass-Now:" in data, f"custom password prompt missing: {data!r}"


def test_block_level_ctext_delivered_after_login(tmp_path: Path):
    """``CTEXT=...`` inside the Telnet CONFIG block is sent to telnet
    users right after a successful login (in addition to the standard
    ``Connected to …`` welcome banner)."""
    cfg = _telnet_cfg_with(
        " CTEXT=Block-level Connect Text\\n Second line"
    )
    with LinbpqInstance(tmp_path, config_template=cfg) as linbpq:
        with socket.create_connection(("127.0.0.1", linbpq.telnet_port), timeout=3) as sock:
            _read_until(sock, b"user:")
            sock.sendall(b"test\r")
            _read_until(sock, b"password:")
            sock.sendall(b"test\r")
            data = _read_until(sock, b"Connect Text", timeout=3)
    assert b"Block-level Connect Text" in data, (
        f"block-level CTEXT missing: {data!r}"
    )


def test_logging_produces_telnet_log_file(tmp_path: Path):
    """``LOGGING=1`` in the Telnet CONFIG block produces a
    ``logs/Telnet_<YYMMDD>.log`` file recording connection events
    (incoming connect, user, accepted, disconnect)."""
    cfg = _telnet_cfg_with(" LOGGING=1")
    with LinbpqInstance(tmp_path, config_template=cfg) as linbpq:
        # Make a quick connection so there's something to log.
        with socket.create_connection(("127.0.0.1", linbpq.telnet_port), timeout=3) as sock:
            _read_until(sock, b"user:")
            sock.sendall(b"test\r")
            _read_until(sock, b"password:")
            sock.sendall(b"test\r")
            _read_until(sock, b"Telnet Server\r\n\r\n", timeout=3)
            sock.sendall(b"BYE\r")
            time.sleep(0.5)

        # Telnet log file is named Telnet_<YYMMDD>.log under logs/.
        logs_dir = tmp_path / "logs"
        log_files = list(logs_dir.glob("Telnet_*.log"))
        assert log_files, (
            f"no Telnet_*.log under {logs_dir}; "
            f"contents: {list(logs_dir.iterdir()) if logs_dir.exists() else 'no logs dir'}"
        )

        contents = log_files[0].read_text(errors="replace")
    assert "Incoming Connect" in contents, (
        f"connect not logged: {contents!r}"
    )
    assert "User=test" in contents, f"user not logged: {contents!r}"
    assert "Call Accepted" in contents, f"accept not logged: {contents!r}"


def test_cms_accepted_cleanly(tmp_path: Path):
    """``CMS=1`` enables the Winlink CMS connection.  Full
    behavioural validation needs a Winlink CMS server simulator
    (out of scope for the gap-analysis closeout); this canary
    just confirms the cfg parser accepts the keyword.

    Also tests CMSCALL / CMSPASS / CMSLOC / CMSSERVER are all
    accepted alongside.
    """
    cfg = _telnet_cfg_with(
        " CMS=1\n"
        " CMSCALL=N0CALL\n"
        " CMSPASS=password123\n"
        " CMSLOC=IO91WJ\n"
        " CMSSERVER=cms.winlink.org"
    )
    with LinbpqInstance(tmp_path, config_template=cfg) as linbpq:
        with socket.create_connection(("127.0.0.1", linbpq.telnet_port), timeout=3) as sock:
            data = _read_until(sock, b"user:", timeout=3)
            assert b"user:" in data
    log = (tmp_path / "linbpq.stdout.log").read_text(errors="replace")
    for keyword in ("CMS", "CMSCALL", "CMSPASS", "CMSLOC", "CMSSERVER"):
        assert (
            f"Ignored:{keyword}" not in log
            and f"Ignored: {keyword}" not in log
        ), f"{keyword} got 'not recognised - Ignored': {log[:2000]}"


def test_relayappl_accepted_cleanly(tmp_path: Path):
    """``RELAYAPPL=<APP>`` declares the application FBB-style relay
    connections should land in.  Accepted-cleanly canary; behaviour
    needs an FBB connection + configured BBS to validate fully."""
    cfg = _telnet_cfg_with(" RELAYAPPL=BBS")
    with LinbpqInstance(tmp_path, config_template=cfg) as linbpq:
        with socket.create_connection(("127.0.0.1", linbpq.telnet_port), timeout=3) as sock:
            data = _read_until(sock, b"user:", timeout=3)
            assert b"user:" in data
    log = (tmp_path / "linbpq.stdout.log").read_text(errors="replace")
    assert "Ignored:RELAYAPPL" not in log and "Ignored: RELAYAPPL" not in log, (
        f"RELAYAPPL got 'not recognised - Ignored': {log[:2000]}"
    )


def test_secure_telnet_disconnect_on_close_localnet_accepted_cleanly(tmp_path: Path):
    """SECURETELNET / DisconnectOnClose / LOCALNET are accepted by
    the cfg parser; daemon boots and serves telnet normally.

    Behaviour driven by these keywords is hard to validate without
    source-IP spoofing (LOCALNET) or scripting client lifecycle
    (DisconnectOnClose); the canary just confirms the cfg lines
    don't break parsing.
    """
    cfg = _telnet_cfg_with(
        " SECURETELNET=1\n"
        " DisconnectOnClose=1\n"
        " LOCALNET=10.45.0.0/24\n"
        " LOCALNET=127.0.0.0/8"
    )
    with LinbpqInstance(tmp_path, config_template=cfg) as linbpq:
        # Telnet still listens.
        with socket.create_connection(("127.0.0.1", linbpq.telnet_port), timeout=3) as sock:
            data = _read_until(sock, b"user:", timeout=3)
            assert b"user:" in data

    # No "not recognised - Ignored" warnings for these keywords.
    log = (tmp_path / "linbpq.stdout.log").read_text(errors="replace")
    for keyword in ("SECURETELNET", "DisconnectOnClose", "LOCALNET"):
        assert f"Ignored:{keyword}" not in log and (
            f"Ignored: {keyword}" not in log
        ), f"{keyword} got 'not recognised - Ignored': {log[:2000]}"
