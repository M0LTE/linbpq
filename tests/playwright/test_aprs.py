"""APRS HTTP coverage.

Uses the ``linbpq_web_with_aprs`` fixture which adds an
``APRSPORT`` / ``APRSCALL`` config and a loopback APRS port —
without that, every /APRS/* page renders as "APRS not configured".

Note that under our minimal test config, the APRS subsystem
doesn't initialise far enough to allocate ``SMEM`` (the APRS
shared-memory block).  This means every endpoint that derefs
``SMEM->Messages`` segfaults — see M0LTE/linbpq#20 for the
NULL-guard issue.

We restrict coverage here to endpoints that don't touch SMEM:
the /APRS root and /aprs/entermsg form.  The msg-list endpoints
will get coverage when #20 is fixed (or when we ship a fixture
with a fully-wired APRS port).
"""

from __future__ import annotations

import pytest

from web_helpers import http_get, http_post


def test_aprs_root_serves(linbpq_web_with_aprs):
    """``/APRS`` should serve the APRS top-level page."""
    port = linbpq_web_with_aprs["http_port"]
    status, body = http_get(port, "/APRS")
    assert b"200" in status, f"GET /APRS: {status!r}"
    assert b"<" in body[:50]


def test_aprs_entermsg_form(linbpq_web_with_aprs):
    """``/aprs/entermsg`` GET serves the enter-message form."""
    port = linbpq_web_with_aprs["http_port"]
    status, body = http_get(port, "/aprs/entermsg")
    assert b"200" in status
    # Form-bearing pages should have an input or a textarea or a form.
    assert b"<form" in body or b"<input" in body or b"<textarea" in body


def test_aprs_works_without_aprs_port(linbpq_web):
    """The non-APRS fixture (no APRSPORT/APRSCALL) should still
    let /APRS/* paths return *some* response — typically a "not
    configured" page or an empty stub.  The strong assertion: it
    doesn't crash and doesn't return 912 NULs."""
    port = linbpq_web["http_port"]
    status, body = http_get(port, "/APRS")
    assert b"HTTP/1.1" in status
    # No NULs in body
    assert b"\x00\x00\x00\x00" not in body[:200], (
        f"got NUL bytes — uninitialised buffer: {body[:80]!r}"
    )


# ── Endpoints blocked by M0LTE/linbpq#20 ─────────────────────────


@pytest.mark.skip(
    reason=(
        "Blocked by M0LTE/linbpq#20: /aprs/msgs, /aprs/txmsgs, "
        "/aprs/find.cgi and /aprsdata.txt deref SMEM->Messages "
        "without a NULL guard.  Under our minimal APRS config, "
        "SMEM never gets allocated.  Re-enable when #20 is fixed "
        "or we ship a fully-wired APRS fixture."
    )
)
def test_aprs_smem_endpoints_when_unblocked(linbpq_web_with_aprs):
    """Placeholder — see skip reason."""
    port = linbpq_web_with_aprs["http_port"]
    for path in ("/aprs/msgs", "/aprs/txmsgs", "/aprsdata.txt"):
        status, body = http_get(port, path)
        assert b"200" in status, f"GET {path}: {status!r}"
