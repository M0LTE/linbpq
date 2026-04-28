"""Smoke test for the linbpq_web_with_aprs fixture.

Confirms the APRS-enabled boot sequence works and at least the
top-level /APRS/ page is reachable.  Real coverage of the APRS
templates lives in test_aprs.py.
"""

from __future__ import annotations

from web_helpers import http_get


def test_aprs_fixture_boots(linbpq_web_with_aprs):
    port = linbpq_web_with_aprs["http_port"]
    status, _ = http_get(port, "/Node/NodeIndex.html")
    assert b"200" in status, f"node index broken with APRS enabled: {status!r}"
