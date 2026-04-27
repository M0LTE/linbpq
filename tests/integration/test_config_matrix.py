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


# Empirically, comment-handling differs by scope:
#
# - Top-level: ``;`` is a clean comment marker.  ``#`` lines land
#   in the unknown-keyword path and produce "not recognised -
#   Ignored" warnings (harmless but noisy).
# - PORT block (before CONFIG): only ``;``-style is clean.
# - Inside CONFIG (driver-specific block): both ``#`` and ``;``
#   are silently skipped by ``TelnetV6.c::ProcessLine`` and the
#   embedded-CONFIG line iterator.
WITH_SEMI_COMMENTS = Template(
    """\
; Semicolon comment at top — proper comment marker
;

SIMPLE=1
NODECALL=N0CALL
; Comment between top-level keywords
NODEALIAS=TEST
LOCATOR=NONE

PORT
 ; Comment in PORT block (semicolon-style)
 ID=Telnet
 DRIVER=Telnet
 CONFIG
 # Hash comment inside CONFIG (accepted here)
 ; Semicolon comment inside CONFIG
 TCPPORT=$telnet_port
 HTTPPORT=$http_port
 MAXSESSIONS=10
 USER=test,test,N0CALL,,SYSOP
ENDPORT
"""
)


def test_semicolon_comments_are_silently_ignored(tmp_path):
    """``;`` at top level and ``#``/``;`` inside blocks are accepted
    cleanly — no "Ignored" warnings in the boot log."""
    from helpers.telnet_client import TelnetClient as _TC

    with LinbpqInstance(tmp_path, config_template=WITH_SEMI_COMMENTS) as linbpq:
        with _TC("127.0.0.1", linbpq.telnet_port) as client:
            client.login("test", "test")
            response = client.run_command("VERSION")
        assert b"Version" in response

    log = (tmp_path / "linbpq.stdout.log").read_text(errors="replace")
    assert "Ignored" not in log, (
        f"comments produced 'Ignored' warnings; log:\n{log[:2000]}"
    )


WITH_HASH_COMMENT_TOP_LEVEL = Template(
    """\
# Hash comment — at top level this lands in the unknown-keyword path
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
 MAXSESSIONS=10
 USER=test,test,N0CALL,,SYSOP
ENDPORT
"""
)


LOWERCASE_KEYWORDS = Template(
    """\
simple=1
nodecall=N0CALL
nodealias=TEST
locator=NONE

port
 ID=Telnet
 driver=Telnet
 config
 tcpport=$telnet_port
 httpport=$http_port
 maxsessions=10
 user=test,test,N0CALL,,SYSOP
endport
"""
)


def test_keywords_are_case_insensitive(tmp_path):
    """``simple`` / ``nodecall`` / ``port`` / ``driver`` / ``tcpport``
    in any case are accepted and the daemon boots normally."""
    from helpers.telnet_client import TelnetClient as _TC

    with LinbpqInstance(
        tmp_path, config_template=LOWERCASE_KEYWORDS
    ) as linbpq:
        with _TC("127.0.0.1", linbpq.telnet_port) as client:
            client.login("test", "test")
            response = client.run_command("VERSION")
        assert b"Version" in response


# Trailing spaces on top-level keywords and inside CONFIG must be
# tolerated so a copy-pasted cfg from a doc with stray whitespace
# doesn't silently break.  Note the deliberate trailing spaces on
# several lines below.
TRAILING_WHITESPACE = Template(
    "SIMPLE=1   \n"
    "NODECALL=N0CALL   \n"
    "NODEALIAS=TEST\n"
    "LOCATOR=NONE\n"
    "\n"
    "PORT\n"
    " ID=Telnet\n"
    " DRIVER=Telnet\n"
    " CONFIG\n"
    " TCPPORT=$telnet_port   \n"
    " HTTPPORT=$http_port\n"
    " MAXSESSIONS=10\n"
    " USER=test,test,N0CALL,,SYSOP\n"
    "ENDPORT\n"
)


def test_trailing_whitespace_is_tolerated(tmp_path):
    """Trailing spaces on keyword=value lines don't break parsing."""
    from helpers.telnet_client import TelnetClient as _TC

    with LinbpqInstance(
        tmp_path, config_template=TRAILING_WHITESPACE
    ) as linbpq:
        with _TC("127.0.0.1", linbpq.telnet_port) as client:
            client.login("test", "test")
            response = client.run_command("VERSION")
        assert b"Version" in response


def test_hash_comment_at_top_level_is_warned_but_tolerated(tmp_path):
    """Top-level ``#`` lines log 'not recognised - Ignored' but the
    daemon boots and serves telnet anyway.  Locks in current
    behaviour; if upstream chooses to honour ``#`` at top level the
    test flips and we'll know."""
    from helpers.telnet_client import TelnetClient as _TC

    with LinbpqInstance(
        tmp_path, config_template=WITH_HASH_COMMENT_TOP_LEVEL
    ) as linbpq:
        with _TC("127.0.0.1", linbpq.telnet_port) as client:
            client.login("test", "test")
            response = client.run_command("VERSION")
        assert b"Version" in response

    log = (tmp_path / "linbpq.stdout.log").read_text(errors="replace")
    assert "Ignored: # Hash comment" in log, (
        f"expected the # line to be treated as unknown keyword: "
        f"{log[:1500]}"
    )
