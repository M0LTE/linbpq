"""Phase 2 — canary tests that the secondary TCP channels open at all.

These are intentionally shallow.  Their purpose is to catch the regression
of "this protocol stopped listening at all" — deeper protocol coverage
lives in dedicated test modules (or arrives in later phases).
"""

from __future__ import annotations

import socket


def _can_open(port: int, timeout: float = 2.0) -> None:
    with socket.create_connection(("127.0.0.1", port), timeout=timeout):
        return


def test_netrom_tcp_port_listens(linbpq):
    """NET/ROM-over-TCP accepts new connections."""
    _can_open(linbpq.netrom_port)


def test_fbb_tcp_port_listens(linbpq):
    """FBB host-mode TCP accepts new connections."""
    _can_open(linbpq.fbb_port)


def test_api_port_listens(linbpq):
    """The HTTP-based JSON API port accepts new connections."""
    _can_open(linbpq.api_port)
