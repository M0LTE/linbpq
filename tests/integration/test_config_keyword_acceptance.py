"""Cfg keywords that are accepted but don't have a clean
runtime read-back path.

For each, we assert: linbpq parses the keyword without emitting
"not recognised - Ignored" warnings and the daemon boots
normally (telnet listens, basic command works).  Where there's a
side-effect we *can* see (e.g. LINMAIL produces a "Mail Started"
log line), we lock that in too.

This is a regression net for "the parser silently dropped this
keyword in a refactor" — a weak invariant on its own, but
combined with the other tests it's strong.
"""

from __future__ import annotations

from pathlib import Path
from string import Template

import pytest

from helpers.linbpq_instance import LinbpqInstance
from helpers.telnet_client import TelnetClient


def _cfg_with_top_level(extras: str, ipgw_extras: str = "") -> Template:
    ipgw = ""
    if ipgw_extras:
        ipgw = f"\n\nIPGATEWAY\nADAPTER 192.168.99.1 255.255.255.0\n{ipgw_extras}\n****\n"
    return Template(
        f"""\
SIMPLE=1
NODECALL=N0CALL
NODEALIAS=TEST
LOCATOR=NONE
{extras}

PORT
 ID=Telnet
 DRIVER=Telnet
 CONFIG
 TCPPORT=$telnet_port
 HTTPPORT=$http_port
 MAXSESSIONS=10
 USER=test,test,N0CALL,,SYSOP
ENDPORT
{ipgw}"""
    )


def _assert_boots_clean(linbpq: LinbpqInstance) -> None:
    with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
        client.login("test", "test")
        response = client.run_command("VERSION")
    assert b"Version" in response


KEYWORDS_TOP_LEVEL = [
    pytest.param("AUTOSAVE=1", id="AUTOSAVE"),
    pytest.param("L4Compress=1", id="L4Compress"),
    pytest.param("L2COMPRESS=1", id="L2COMPRESS"),
    pytest.param("T3=300", id="T3"),
    pytest.param(
        "MAPCOMMENT=https://example.org/N0CALL", id="MAPCOMMENT"
    ),
    pytest.param("EnableEvents=1", id="EnableEvents"),
    pytest.param("EnableM0LTEMap=1", id="EnableM0LTEMap"),
    pytest.param("ENABLEOARCAPI=1", id="ENABLEOARCAPI"),
]


@pytest.mark.parametrize("cfg_line", KEYWORDS_TOP_LEVEL)
def test_top_level_keyword_accepted(tmp_path: Path, cfg_line: str):
    cfg = _cfg_with_top_level(cfg_line)
    with LinbpqInstance(tmp_path, config_template=cfg) as linbpq:
        _assert_boots_clean(linbpq)
    log = (tmp_path / "linbpq.stdout.log").read_text(errors="replace")
    keyword = cfg_line.split("=")[0]
    assert f"Ignored:{keyword}" not in log and (
        f"Ignored: {keyword}" not in log
    ), f"{keyword} got 'not recognised - Ignored': {log[:2000]}"


def test_idmsg_block_parses_cleanly(tmp_path: Path):
    """``IDMSG:`` ... ``***`` multi-line block with ``IDINTERVAL`` is
    accepted; daemon serves telnet.  Runtime emission is exercised
    separately in ``test_long_runtime_beacons.py`` (one ~2-minute
    boot covers both ID and BT in one test, marked
    ``@pytest.mark.long_runtime`` so xdist runs it in parallel)."""
    cfg = Template(
        """\
SIMPLE=1
NODECALL=N0CALL
NODEALIAS=TEST
LOCATOR=NONE
IDINTERVAL=15

IDMSG:
N0CALL ID Test
Multi-line ID body
***

PORT
 ID=Telnet
 DRIVER=Telnet
 CONFIG
 TCPPORT=$telnet_port
 HTTPPORT=$http_port
 MAXSESSIONS=10
 USER=test,test,N0CALL,,SYSOP
ENDPORT
"""
    )
    with LinbpqInstance(tmp_path, config_template=cfg) as linbpq:
        _assert_boots_clean(linbpq)
    log = (tmp_path / "linbpq.stdout.log").read_text(errors="replace")
    assert "Ignored" not in log, f"IDMSG block rejected: {log[:2000]}"


def test_btext_block_parses_cleanly(tmp_path: Path):
    """``BTEXT:`` ... ``***`` multi-line block with ``BTINTERVAL`` is
    accepted; daemon serves telnet.  Runtime emission covered in
    ``test_long_runtime_beacons.py``."""
    cfg = Template(
        """\
SIMPLE=1
NODECALL=N0CALL
NODEALIAS=TEST
LOCATOR=NONE
BTINTERVAL=5

BTEXT:
!5126.84N/00101.61WBeacon test
***

PORT
 ID=Telnet
 DRIVER=Telnet
 CONFIG
 TCPPORT=$telnet_port
 HTTPPORT=$http_port
 MAXSESSIONS=10
 USER=test,test,N0CALL,,SYSOP
ENDPORT
"""
    )
    with LinbpqInstance(tmp_path, config_template=cfg) as linbpq:
        _assert_boots_clean(linbpq)
    log = (tmp_path / "linbpq.stdout.log").read_text(errors="replace")
    assert "Ignored" not in log, f"BTEXT block rejected: {log[:2000]}"


def test_ipgw_enablesnmp_accepted(tmp_path: Path):
    """``ENABLESNMP`` inside the IPGATEWAY block is accepted."""
    cfg = _cfg_with_top_level("", ipgw_extras="ENABLESNMP")
    with LinbpqInstance(tmp_path, config_template=cfg) as linbpq:
        _assert_boots_clean(linbpq)
    log = (tmp_path / "linbpq.stdout.log").read_text(errors="replace")
    assert "bad config record" not in log.lower(), (
        f"IP gateway parser rejected ENABLESNMP: {log[:2000]}"
    )


def test_linmail_cfg_keyword_starts_mail(tmp_path: Path):
    """``LINMAIL`` at top level starts the mail subsystem
    (equivalent to passing the ``mail`` cli arg)."""
    cfg = Template(
        """\
SIMPLE=1
NODECALL=N0CALL
NODEALIAS=TEST
LOCATOR=NONE
LINMAIL
APPLICATIONS=BBS
BBSCALL=N0BBS
BBSALIAS=BBS

PORT
 ID=Telnet
 DRIVER=Telnet
 CONFIG
 TCPPORT=$telnet_port
 HTTPPORT=$http_port
 MAXSESSIONS=10
 USER=test,test,N0CALL,,SYSOP
ENDPORT
"""
    )
    with LinbpqInstance(tmp_path, config_template=cfg) as linbpq:
        log = (tmp_path / "linbpq.stdout.log").read_bytes()
    assert b"Starting Mail" in log, (
        f"LINMAIL did not start the mail subsystem: {log[-500:]!r}"
    )
    assert b"Mail Started" in log


def test_linchat_cfg_keyword_starts_chat(tmp_path: Path):
    """``LINCHAT`` at top level starts the chat subsystem
    (equivalent to passing the ``chat`` cli arg)."""
    from helpers.linbpq_instance import CHAT_CONFIG_FILE

    cfg = Template(
        """\
SIMPLE=1
NODECALL=N0CALL
NODEALIAS=TEST
LOCATOR=NONE
LINCHAT
APPLICATIONS=CHAT
APPL1CALL=N0CHAT
APPL1ALIAS=CHT

PORT
 ID=Telnet
 DRIVER=Telnet
 CONFIG
 TCPPORT=$telnet_port
 HTTPPORT=$http_port
 MAXSESSIONS=10
 USER=test,test,N0CALL,,SYSOP
ENDPORT
"""
    )
    # Pre-write chatconfig.cfg with the right ApplNum so chat doesn't
    # bail with "No APPLCALL for Chat APPL".
    (tmp_path / "chatconfig.cfg").write_text(CHAT_CONFIG_FILE)
    with LinbpqInstance(tmp_path, config_template=cfg) as linbpq:
        log = (tmp_path / "linbpq.stdout.log").read_bytes()
    assert b"Starting Chat" in log, (
        f"LINCHAT did not start the chat subsystem: {log[-500:]!r}"
    )
    assert b"Chat Started" in log
