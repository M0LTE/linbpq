"""Phase 2 — AGW TCP: version handshake."""

from __future__ import annotations

from helpers.agw_client import request_version


def test_agw_version_request(linbpq):
    """Sending an 'R' frame returns the AGW version constants from AGWAPI.c."""
    major, minor = request_version("127.0.0.1", linbpq.agw_port)
    # AGWAPI.c hard-codes AGWVersion = {2003, 999}; lock that in so any
    # change is intentional.
    assert (major, minor) == (2003, 999), (
        f"unexpected AGW version: {major}.{minor}"
    )
