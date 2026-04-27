"""Phase 4 (second half) — Chat node lifecycle.

Linbpq embeds the BPQ chat-server code (despite ``bpqchat`` shipping
as its own binary too); pass ``chat`` on the command line and
register Chat as an APPLICATIONS slot, and the ``CHAT`` alias at the
node prompt enters the chat-server's parser.

Chat commands all start with ``/`` (e.g. ``/U`` users, ``/T`` topics,
``/H`` help).  Locking in the basic lifecycle: enter, register name,
get welcome banner, list users, browse topics, get help.
"""

from __future__ import annotations

from helpers.telnet_client import TelnetClient


def _enter_chat(client: TelnetClient) -> bytes:
    """Authenticate, enter CHAT, register a name; return the welcome
    block (which includes the user list)."""
    client.login("test", "test")
    client.write_line("CHAT")
    client.read_until(b"Please enter your Name", timeout=5)
    client.read_until(b">", timeout=5)
    client.write_line("Tester")
    # Welcome message + station list arrives in one block.
    return client.read_idle(idle_timeout=1.0, max_total=4.0)


def test_chat_alias_appears_in_help(linbpq_chat):
    """``?`` at the node prompt now lists CHAT."""
    with TelnetClient("127.0.0.1", linbpq_chat.telnet_port) as client:
        client.login("test", "test")
        response = client.run_command("?")
    assert b"CHAT" in response, f"CHAT not in ? response: {response!r}"


def test_chat_enter_and_welcome(linbpq_chat):
    """Enter chat, register a name, see the configured welcome banner
    and ourselves listed as a connected station."""
    with TelnetClient("127.0.0.1", linbpq_chat.telnet_port) as client:
        welcome = _enter_chat(client)
    assert b"Welcome to the test chat node!" in welcome, (
        f"welcome banner missing: {welcome!r}"
    )
    assert b"Tester" in welcome, f"user not listed: {welcome!r}"
    assert b"Station(s) connected" in welcome


def test_chat_help_lists_commands(linbpq_chat):
    """``/H`` prints the chat-server help block."""
    with TelnetClient("127.0.0.1", linbpq_chat.telnet_port) as client:
        _enter_chat(client)
        client.write_line("/H")
        response = client.read_idle(idle_timeout=1.0, max_total=4.0)
    # Help text is multi-line; assert on a few of the documented
    # commands rather than the exact wording.
    assert b"/U - Show Users" in response, (
        f"chat help missing /U: {response!r}"
    )
    assert b"/T" in response and b"Topic" in response, (
        f"chat help missing /T topic: {response!r}"
    )


def test_chat_users_command_lists_self(linbpq_chat):
    """``/U`` returns the user list; we should see ourselves."""
    with TelnetClient("127.0.0.1", linbpq_chat.telnet_port) as client:
        _enter_chat(client)
        client.write_line("/U")
        response = client.read_idle(idle_timeout=1.0, max_total=4.0)
    assert b"Tester" in response, f"self not in /U output: {response!r}"


def test_chat_topic_create_and_list(linbpq_chat):
    """``/T <name>`` creates / joins a topic; ``/T`` lists topics."""
    with TelnetClient("127.0.0.1", linbpq_chat.telnet_port) as client:
        _enter_chat(client)
        client.write_line("/T testroom")
        client.read_idle(idle_timeout=1.0, max_total=3.0)
        client.write_line("/T")
        topics = client.read_idle(idle_timeout=1.0, max_total=3.0)
    assert b"testroom" in topics or b"TESTROOM" in topics, (
        f"new topic not in topic list: {topics!r}"
    )


def test_chat_invalid_command_is_rejected(linbpq_chat):
    """Unrecognised slash-commands return 'Invalid Command'.

    Note: the chat parser uses single-letter commands followed by
    arguments — so ``/NOSUCH`` would be parsed as ``/N OSUCH`` (set
    name).  ``/W`` is genuinely unrecognised at the time of writing.
    """
    with TelnetClient("127.0.0.1", linbpq_chat.telnet_port) as client:
        _enter_chat(client)
        client.write_line("/W")
        response = client.read_idle(idle_timeout=1.0, max_total=3.0)
    assert b"Invalid Command" in response, (
        f"unknown command not rejected cleanly: {response!r}"
    )
