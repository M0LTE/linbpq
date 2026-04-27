"""Phase 4 — BBS lifecycle: enter, register name, list / read / kill.

Linbpq's BBS is the BPQMail subsystem inside ``linbpq.bin`` — enabled
by passing ``mail`` on the command line and registering the BBS as an
``APPLICATIONS=BBS`` entry with ``BBSCALL`` / ``BBSALIAS`` set.

These tests use the ``linbpq_mail`` fixture (see conftest.py) which
turns those on.  Each test enters the BBS via the telnet ``BBS``
command and drives the BBS' own command parser.
"""

from __future__ import annotations

import time

from helpers.telnet_client import TelnetClient


def _enter_bbs(client: TelnetClient) -> bytes:
    """Authenticate as a sysop user and enter the BBS application.

    First-time users are prompted for their name.  Returns everything
    received including the name-registration block, ending at the BBS
    command prompt ``de N0CALL>``.
    """
    client.login("test", "test")
    client.write_line("BBS")
    # The BBS sends a banner ending with "Please enter your Name\r\n>"
    client.read_until(b"Please enter your Name", timeout=5)
    client.read_until(b">", timeout=5)
    client.write_line("Tester")
    # First-time login also nudges the user to set HomeBBS / QTH / ZIP,
    # then drops to the BBS prompt ``de <call>>``.
    return client.read_until(b"de N0CALL>", timeout=5)


def test_bbs_alias_appears_in_help(linbpq_mail):
    """``?`` at the node prompt now lists BBS."""
    with TelnetClient("127.0.0.1", linbpq_mail.telnet_port) as client:
        client.login("test", "test")
        response = client.run_command("?")
    assert b"BBS" in response, f"BBS not in ? response: {response!r}"


def test_bbs_enter_and_help(linbpq_mail):
    """Enter the BBS, register a name, send ``H`` for help."""
    with TelnetClient("127.0.0.1", linbpq_mail.telnet_port) as client:
        _enter_bbs(client)
        client.write_line("H")
        help_text = client.read_until(b"de N0CALL>", timeout=5)
    # The BPQMail help block lists single-letter commands.
    assert b"L - List Message" in help_text, (
        f"BBS H did not return the help block: {help_text!r}"
    )
    assert b"K - Kill Message" in help_text


def test_bbs_info_command(linbpq_mail):
    """``I`` prints the configured INFO file or 'no INFO' when absent."""
    with TelnetClient("127.0.0.1", linbpq_mail.telnet_port) as client:
        _enter_bbs(client)
        client.write_line("I")
        info = client.read_until(b"de N0CALL>", timeout=5)
    assert (
        b"SYSOP has not created an INFO file" in info
        or b"INFO" in info
    ), f"unexpected INFO response: {info!r}"


def test_bbs_list_when_empty(linbpq_mail):
    """``L`` lists messages; with a fresh BBS there are none."""
    with TelnetClient("127.0.0.1", linbpq_mail.telnet_port) as client:
        registration = _enter_bbs(client)
        # Registration block on first login confirms the message numbering
        # is at zero.
        assert b"Latest Message is 0" in registration, (
            f"unexpected registration: {registration!r}"
        )
        client.write_line("L")
        # On an empty BBS the L command falls through quickly to the
        # next prompt with no message lines.
        response = client.read_until(b"de N0CALL>", timeout=5)
    assert b"de N0CALL>" in response


def test_bbs_logoff_returns_to_node(linbpq_mail):
    """``B`` from inside the BBS exits back to the node session."""
    with TelnetClient("127.0.0.1", linbpq_mail.telnet_port) as client:
        _enter_bbs(client)
        client.write_line("B")
        # BPQMail sends a "Disconnected" message on logoff.
        response = client.read_until(b"Disconnected", timeout=5)
    assert b"Disconnected" in response


def test_bbs_message_round_trip(linbpq_mail):
    """SP / Title / Body / /EX writes a message; R reads it; K kills it.

    Locks in the full BBS persistence path inside the running daemon —
    a refactor that breaks the message-store gets caught here.
    """
    with TelnetClient("127.0.0.1", linbpq_mail.telnet_port) as client:
        _enter_bbs(client)

        # Send Personal to TEST.  BBS prompts: title, then body, end /EX.
        client.write_line("SP TEST")
        client.read_until(b"Enter Title", timeout=5)
        client.write_line("regression-test-subject")
        client.read_until(b"Enter Message Text", timeout=5)
        client.write_line("regression-test-body")
        # BPQMail needs a beat to ingest the body before recognising
        # /EX as end-of-message; without the pause both lines arrive
        # in the same read() and /EX is consumed as message text.
        time.sleep(0.5)
        client.write_line("/EX")
        save_response = client.read_until(b"de N0CALL>", timeout=10)
        # On save, BPQMail prints "Message: <N> Bid: <bid> Size: <bytes>".
        assert b"Message: 1 Bid:" in save_response, (
            f"SP did not save with expected confirmation: {save_response!r}"
        )

        # Read it back.
        client.write_line("R 1")
        read_response = client.read_until(b"de N0CALL>", timeout=5)
        assert b"Title: regression-test-subject" in read_response, (
            f"title mismatch on read: {read_response!r}"
        )
        assert b"regression-test-body" in read_response, (
            f"body missing on read: {read_response!r}"
        )
        assert b"To: TEST" in read_response

        # Kill it.
        client.write_line("K 1")
        kill_response = client.read_until(b"de N0CALL>", timeout=5)
        assert b"Killed" in kill_response, (
            f"K did not confirm kill: {kill_response!r}"
        )
