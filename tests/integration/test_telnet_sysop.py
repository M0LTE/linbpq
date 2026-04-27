"""Phase 3 — sysop gating.

Three invariants:

1. A non-sysop logged-in user is rejected from sysop commands.
2. A SYSOP-flagged user is *also* rejected from sysop commands until
   they run ``PASSWORD``.  The Cmd.c gate is ``Session->PASSWORD ==
   0xFFFF``, set only by ``PWDCMD``.
3. After a SYSOP-flagged user runs ``PASSWORD`` (which short-circuits
   to ``Ok`` for ``Secure_Session=1`` users), sysop commands work.

Asserting on the rejection message ``Command requires SYSOP status``
ties the test to a strong invariant: the user-facing string is part of
the contract that authentication is enforced.
"""

from __future__ import annotations

from helpers.telnet_client import TelnetClient

SYSOP_REJECT = b"Command requires SYSOP status"


def test_non_sysop_user_rejected_from_sysop_command(linbpq):
    with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
        client.login("user", "user")
        response = client.run_command("SAVENODES")
    assert SYSOP_REJECT in response, (
        f"non-sysop got past gate: {response!r}"
    )


def test_sysop_user_rejected_until_password_run(linbpq):
    """SYSOP-flagged user still needs to run PASSWORD before sysop cmds."""
    with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
        client.login("test", "test")
        response = client.run_command("SAVENODES")
    assert SYSOP_REJECT in response, (
        f"sysop user got past gate without PASSWORD: {response!r}"
    )


def test_sysop_user_unlocks_with_password_command(linbpq):
    """After PASSWORD, sysop user can run sysop commands."""
    with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
        client.login("test", "test")
        pw_response = client.run_command("PASSWORD")
        # Secure_Session=1 → PWDCMD short-circuits and prints Ok.
        assert b"Ok" in pw_response, f"PASSWORD not Ok: {pw_response!r}"

        savenodes_response = client.run_command("SAVENODES")
    assert SYSOP_REJECT not in savenodes_response, (
        f"still gated after PASSWORD: {savenodes_response!r}"
    )
    # SAVENODES prints a confirmation; just assert prompt + no rejection.
    assert b"TEST:N0CALL}" in savenodes_response


def test_non_sysop_password_returns_challenge(linbpq):
    """For a non-sysop, PASSWORD prints a 5-number challenge they can't
    answer; PWDCMD goes through its non-Secure_Session branch."""
    with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
        client.login("user", "user")
        response = client.run_command("PASSWORD")
    # The challenge is five space-separated indices into the configured
    # password text.  Without an SYSPASS configured the values are all 1.
    assert b"Ok" not in response, f"non-sysop got Ok: {response!r}"
    assert SYSOP_REJECT not in response, (
        f"PASSWORD itself should not be sysop-gated: {response!r}"
    )


def test_savemh_after_unlock_succeeds(linbpq):
    """SAVEMH (parallel of SAVENODES) returns Ok for an unlocked sysop."""
    with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
        client.login("test", "test")
        client.run_command("PASSWORD")
        response = client.run_command("SAVEMH")
    assert b"Ok" in response, f"SAVEMH did not return Ok: {response!r}"
    assert SYSOP_REJECT not in response


import pytest


@pytest.mark.parametrize(
    "cmd",
    [
        "REBOOT",
        "RESTART",
        "RESTARTTNC",
        "RIGRECONFIG",
        "TELRECONFIG",
        "STOPCMS",
        "STARTCMS",
        "EXTRESTART",
    ],
)
def test_side_effect_commands_sysop_gated(linbpq, cmd):
    """Sysop-only commands with side effects (restart, reconfigure,
    bring CMS up/down, etc.) — non-sysop users get the standard
    ``Command requires SYSOP status`` rejection.

    We deliberately don't exercise the unlocked path: triggering any
    of these would either take the daemon down mid-test or
    re-initialise something we don't have the cleanup machinery to
    restore. The sysop-gating canary locks in (a) the parser
    recognises the command word and (b) authentication is required —
    enough to flag a regression that broke the gate."""
    with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
        client.login("user", "user")
        response = client.run_command(cmd)
    assert SYSOP_REJECT in response, (
        f"{cmd} not sysop-gated: {response!r}"
    )


def test_getportctext_reads_per_port_files(tmp_path, linbpq):
    """``GETPORTCTEXT`` re-reads per-port ``Port<N>CTEXT.txt`` files
    from the working directory into ``PORT->CTEXT`` (CommonCode.c:4898).

    Pre-writes a per-port CTEXT file then runs the sysop command —
    the response lists the ports it loaded text for.
    """
    # Write CTEXT for port 1 (the Telnet port in our default config).
    (linbpq.work_dir / "Port1CTEXT.txt").write_text(
        "Welcome from getportctext test\n"
        "Second line of CTEXT\n"
    )

    with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
        client.login("test", "test")
        client.run_command("PASSWORD")
        response = client.run_command("GETPORTCTEXT")

    assert SYSOP_REJECT not in response, (
        f"sysop unlocked but still rejected: {response!r}"
    )
    assert b"CTEXT Read for ports" in response, (
        f"GETPORTCTEXT didn't echo expected confirmation: {response!r}"
    )
    # The port-list in the response is the ports that had a file
    # loaded — must include port 1.
    assert b"1" in response, (
        f"port 1 not in GETPORTCTEXT response: {response!r}"
    )


def test_getportctext_with_no_files_returns_empty_list(linbpq):
    """GETPORTCTEXT with no ``Port<N>CTEXT.txt`` files present returns
    the same envelope but with an empty port list."""
    with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
        client.login("test", "test")
        client.run_command("PASSWORD")
        response = client.run_command("GETPORTCTEXT")
    assert b"CTEXT Read for ports" in response, (
        f"GETPORTCTEXT didn't return expected envelope: {response!r}"
    )


def test_dump_command_recognised(linbpq):
    """``DUMP`` is documented as a Windows-build sysop command (writes a
    minidump file).  On Linux the dispatch entry exists but the
    handler is a no-op that returns ``Ok``.  Never crash the session.

    Test asserts the parser recognises the word — distinct from
    ``Invalid command`` or session death.
    """
    with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
        client.login("user", "user")
        response = client.run_command("DUMP")
    assert b"Invalid command" not in response, (
        f"DUMP not recognised by parser: {response!r}"
    )


def test_exclude_command_recognised(linbpq):
    """``EXCLUDE`` is documented as a Windows-build sysop command for
    the connect-exclude list.  On Linux the parser still recognises
    the word; behaviour beyond that depends on build flags.
    """
    with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
        client.login("user", "user")
        response = client.run_command("EXCLUDE")
    assert b"Invalid command" not in response, (
        f"EXCLUDE not recognised by parser: {response!r}"
    )


def test_validcalls_without_port_is_rejected(linbpq):
    """VALIDCALLS is sysop-gated and needs a port number; without one
    the command-handler emits 'Invalid Port Number' rather than help
    text."""
    with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
        client.login("test", "test")
        client.run_command("PASSWORD")
        response = client.run_command("VALIDCALLS")
    assert SYSOP_REJECT not in response, (
        f"sysop-unlocked but VALIDCALLS still gated: {response!r}"
    )
    assert b"Invalid Port" in response, (
        f"VALIDCALLS without port unexpected: {response!r}"
    )
