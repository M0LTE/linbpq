"""Phase 3 — per-session-setting round-trip: read, set, read again."""

from __future__ import annotations

import pytest

from helpers.telnet_client import TelnetClient

# (command, label-in-response, new-value)
# Note the command/label asymmetry on L4T1: the command is ``L4T1`` but
# the label that BPQ prints is ``L4TIMEOUT``.
SESSION_SETTINGS = [
    pytest.param("PACLEN", b"PACLEN", 200, id="PACLEN"),
    pytest.param("IDLETIME", b"IDLETIME", 600, id="IDLETIME"),
    pytest.param("L4T1", b"L4TIMEOUT", 7000, id="L4T1"),
]


@pytest.mark.parametrize("cmd, label, new_value", SESSION_SETTINGS)
def test_session_setting_round_trip(linbpq, cmd, label, new_value):
    """``<cmd>`` reads, ``<cmd> <n>`` writes, second ``<cmd>`` confirms."""
    with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
        client.login("test", "test")

        before = client.run_command(cmd)
        assert label in before, f"label {label!r} not in {before!r}"

        set_resp = client.run_command(f"{cmd} {new_value}")
        assert f"{label.decode()} - {new_value}".encode() in set_resp, (
            f"set did not echo new value: {set_resp!r}"
        )

        after = client.run_command(cmd)
        assert f"{label.decode()} - {new_value}".encode() in after, (
            f"read-back did not match: {after!r}"
        )
