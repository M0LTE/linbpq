"""UZ7HO / QTSM subsystem commands — bare-form error handling.

Bare ``UZ7HO`` used to segfault via ``strlen(NULL)`` in
``Cmd.c::UZ7HOCMD``; the upstream 6.0.25.28 merge added a ``Cmd ==
NULL`` guard so it now returns a usage hint.  See
https://github.com/M0LTE/linbpq/issues/3 (fixed).

Bare ``QTSM`` is the inverse story: previously rejected cleanly
with ``Error - Port 0 is not a KISS port``, but the same upstream
merge added a ``_stricmp(ptr, "HELP")`` check ahead of any null
check on ``ptr`` — so ``strtok_s`` returning NULL on bare QTSM now
crashes the handler.  The fork carries a one-line null-guard
patch (PR #65 against upstream); on branches that include it the
test asserts the recovered behaviour, on branches that don't it
xfails strictly so the moment upstream lands the fix we get a
hard XPASS signal.
"""

from __future__ import annotations

import pathlib

import pytest

from helpers.telnet_client import TelnetClient


def _qtsm_null_guard_present() -> bool:
    """Detect whether this checkout has the fork's QTSMCMD null guard.

    Looks for the ``if (ptr == NULL)`` line we add to ``Cmd.c::QTSMCMD``
    in the patched branch / PR #65.  The integration tests run inside
    the Dockerfile.test container which ``COPY`` s the whole repo to
    ``/src``, so ``Cmd.c`` is at ``<repo_root>/Cmd.c`` in both docker
    and local runs.  Returns False if Cmd.c can't be read for any
    reason (we'd rather xfail-and-investigate than crash test
    collection).
    """
    try:
        cmd_c = pathlib.Path(__file__).resolve().parents[2] / "Cmd.c"
        text = cmd_c.read_text(errors="ignore")
    except OSError:
        return False
    # ``rfind`` (not ``find``): the file has a forward-declaration
    # prototype near the top of Cmd.c (``VOID QTSMCMD(...);``) and
    # the actual function definition much further down.  The first
    # occurrence is the prototype — its 4k-char neighbourhood is
    # nowhere near the function body, so a naive ``find`` always
    # reports "no guard" even when the patched function has one.
    start = text.rfind("VOID QTSMCMD")
    if start < 0:
        return False
    # Function bodies are well under 4k chars; check the head of the
    # function for the guard.
    return "if (ptr == NULL)" in text[start:start + 4000]


_HAS_QTSM_FIX = _qtsm_null_guard_present()


@pytest.mark.xfail(
    condition=not _HAS_QTSM_FIX,
    strict=True,
    reason=(
        "QTSM null-guard fix not in this checkout (upstream PR #65 / "
        "issue #64 pending).  Bare QTSM crashes the user session via "
        "_stricmp(NULL, ...) in Cmd.c::QTSMCMD.  When upstream merges "
        "the fix this xfail flips to XPASS — strict mode then breaks "
        "the suite to prompt removing it."
    ),
)
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
