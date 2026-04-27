"""Phase 3 deferral — BBS / CHAT / MAIL application-alias commands.

Without a configured BBS, Chat or Mail application these aliases fall
through to the generic "Invalid command" branch.  Lock that in so an
accidental wiring of unbound aliases (which would silently look like
they did something) lands the test red.
"""

from __future__ import annotations

import pytest

from helpers.telnet_client import TelnetClient

ALIASES = ["BBS", "CHAT", "MAIL"]


@pytest.mark.parametrize("alias", ALIASES)
def test_unconfigured_app_alias_is_rejected(linbpq, alias):
    with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
        client.login("test", "test")
        response = client.run_command(alias)
    assert b"Invalid command" in response, (
        f"{alias} did not return 'Invalid command' (apps not configured); "
        f"got {response!r}"
    )
