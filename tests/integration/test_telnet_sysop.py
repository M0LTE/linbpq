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
