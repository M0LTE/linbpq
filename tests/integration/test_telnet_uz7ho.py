"""UZ7HO / QTSM subsystem commands — bare-form error handling.

Bare ``UZ7HO`` used to segfault via ``strlen(NULL)`` in
``Cmd.c::UZ7HOCMD``; the upstream 6.0.25.28 merge added a ``Cmd ==
NULL`` guard so it now returns a usage hint.  See
https://github.com/M0LTE/linbpq/issues/3 (fixed).

Bare ``QTSM`` is the inverse story: previously rejected cleanly
with ``Error - Port 0 is not a KISS port``, but the same upstream
merge added a ``_stricmp(ptr, "HELP")`` check ahead of any null
check on ``ptr`` — so ``strtok_s`` returning NULL on bare QTSM now
crashes the handler.  Tracked separately.
"""

from __future__ import annotations

from helpers.telnet_client import TelnetClient


def test_qtsm_without_port_rejected_cleanly(linbpq):
    with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
        client.login("test", "test")
        response = client.run_command("QTSM")
    assert b"not a KISS port" in response, (
        f"QTSM bare didn't return clean error: {response!r}"
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
