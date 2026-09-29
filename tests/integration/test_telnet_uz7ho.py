"""UZ7HO / QTSM subsystem commands — bare-form error handling.

Bare ``UZ7HO`` used to segfault via ``strlen(NULL)`` in
``Cmd.c::UZ7HOCMD``; the upstream 6.0.25.28 merge added a ``Cmd ==
NULL`` guard so it now returns a usage hint.  See
https://github.com/M0LTE/linbpq/issues/3 (fixed).

Bare ``QTSM`` crashed the user session after the same merge:
``strtok_s`` returns NULL and ``_stricmp(NULL, "HELP")`` dereferenced
it.  John fixed that upstream (``if (!ptr || _stricmp(ptr, "HELP") ==
0)``), so bare QTSM now prints the command's help text.
"""

from __future__ import annotations

from helpers.telnet_client import TelnetClient


def test_qtsm_bare_returns_help(linbpq):
    """Bare QTSM prints the help text rather than crashing (issue #64,
    fixed upstream)."""
    with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
        client.login("test", "test")
        response = client.run_command("QTSM")
    assert b"QTSM portno displays QTSM configuration info" in response, (
        f"QTSM bare didn't return help text: {response!r}"
    )


def test_uz7ho_bare_returns_usage_hint(linbpq):
    """Bare UZ7HO returns a usage hint cleanly (issue #3, fixed).

    Was: ``strlop`` returns NULL when CmdTail has no space; the
    follow-up ``strlen(Cmd)`` then segfaulted, killing the listener.
    Now: ``Cmd.c::UZ7HOCMD`` checks ``Cmd == 0`` and emits
    ``Missing params - usage is UZ7HO port Command`` instead.
    """
    with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
        client.login("test", "test")
        response = client.run_command("UZ7HO")
    assert b"usage is UZ7HO" in response, (
        f"UZ7HO bare didn't return usage hint: {response!r}"
    )
