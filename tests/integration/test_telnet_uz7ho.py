"""Phase 3 deferral — UZ7HO / QTSM subsystem commands.

QTSM with no port number rejects cleanly with
``Error - Port 0 is not a KISS port`` — locked in.

Bare UZ7HO crashes linbpq entirely due to a NULL deref in
``Cmd.c::UZ7HOCMD`` (``strlop`` returns NULL when there's no space
in CmdTail; the loop then calls ``strlen(NULL)``).  The SIGSEGV
handler logs a backtrace to the linbpq log but does not recover —
the listener stops accepting connections.  See
https://github.com/M0LTE/linbpq/issues/3.

The test pins the current crash invariant (the daemon stops
accepting telnet connections after a bare UZ7HO) so it goes red
when the upstream fix lands.
"""

from __future__ import annotations

import socket
import time

from helpers.telnet_client import TelnetClient


def test_qtsm_without_port_rejected_cleanly(linbpq):
    with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
        client.login("test", "test")
        response = client.run_command("QTSM")
    assert b"not a KISS port" in response, (
        f"QTSM bare didn't return clean error: {response!r}"
    )


def test_uz7ho_bare_crashes_linbpq(linbpq):
    """Bare UZ7HO segfaults; the listener stops accepting connections.

    Pinned to the current broken behaviour — flip this test to a
    "returns a usage hint" assertion once issue #3 is fixed.
    """
    with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
        client.login("test", "test")
        client.write_line("UZ7HO")
        # No response arrives because the process crashes.
        time.sleep(1.5)

    # New connections to the telnet port now fail.
    try:
        sock = socket.create_connection(
            ("127.0.0.1", linbpq.telnet_port), timeout=2
        )
    except (ConnectionRefusedError, OSError):
        return  # expected — the daemon is dead
    else:
        sock.close()
        raise AssertionError(
            "UZ7HO no longer crashes linbpq — issue #3 may be fixed.  "
            "Update this test to assert on the new sensible response "
            "(probably a usage hint, mirroring QTSM's behaviour)."
        )
