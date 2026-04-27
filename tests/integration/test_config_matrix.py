"""Phase 7 starter — bpq32.cfg variants.

Drives a small matrix of config files to lock in parser behaviour we
don't otherwise see. Each test constructs ``LinbpqInstance`` with a
custom ``Template`` so it can diverge from the default config used by
the rest of the suite.
"""

from __future__ import annotations

from string import Template

from helpers.linbpq_instance import LinbpqInstance
from helpers.telnet_client import TelnetClient


# A genuinely minimal config that will start linbpq.  Empirically the
# parser requires: SIMPLE=1 (so all the optional fields can default),
# NODECALL, LOCATOR (or LOCATOR=NONE), and a PORT block.  Anything less
# triggers "Configuration File Error" and a clean exit with the parser
# spelling out what's missing.
MINIMAL = Template(
    """\
SIMPLE=1
NODECALL=N0CALL
LOCATOR=NONE

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


# Default config plus a junk top-level keyword. The parser is documented
# (and observed) to log "not recognised - Ignored" rather than abort.
WITH_UNKNOWN_KEYWORD = Template(
    """\
SIMPLE=1
NODECALL=N0CALL
NODEALIAS=TEST
LOCATOR=IO91WJ
TOTAL_GIBBERISH=42

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


# Several USER lines — confirm every entry can authenticate independently.
MULTI_USER = Template(
    """\
SIMPLE=1
NODECALL=N0CALL
NODEALIAS=TEST
LOCATOR=IO91WJ

PORT
 ID=Telnet
 DRIVER=Telnet
 CONFIG
 TCPPORT=$telnet_port
 HTTPPORT=$http_port
 MAXSESSIONS=10
 USER=alice,alpha,M0AAA,,
 USER=bob,bravo,M0BBB,,
 USER=charlie,charlie123,M0CCC,,SYSOP
 USER=test,test,N0CALL,,SYSOP
ENDPORT
"""
)


def test_minimal_config_boots(tmp_path):
    with LinbpqInstance(tmp_path, config_template=MINIMAL) as linbpq:
        with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
            data = client.read_until(b"user:")
    assert b"user:" in data


def test_unknown_keyword_is_ignored(tmp_path):
    """A bogus top-level keyword logs an Ignored line but startup continues."""
    with LinbpqInstance(tmp_path, config_template=WITH_UNKNOWN_KEYWORD) as linbpq:
        with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
            client.login("test", "test")
            response = client.run_command("VERSION")
    assert b"Version" in response
    log = (tmp_path / "linbpq.stdout.log").read_text(errors="replace")
    assert "TOTAL_GIBBERISH" in log, (
        f"expected the unknown keyword to appear in the ignored-line warning; "
        f"log was:\n{log[:2000]}"
    )


def test_multi_user_each_can_login(tmp_path):
    creds = [
        ("alice", "alpha"),
        ("bob", "bravo"),
        ("charlie", "charlie123"),
        ("test", "test"),
    ]
    with LinbpqInstance(tmp_path, config_template=MULTI_USER) as linbpq:
        for user, pw in creds:
            with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
                welcome = client.login(user, pw)
                assert b"Connected" in welcome, (
                    f"login as {user} failed; got {welcome!r}"
                )
