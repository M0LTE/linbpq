"""Winlink CMS connectivity probe — beyond cfg-acceptance.

When ``CMS=1`` is set on the Telnet PORT block, linbpq runs a
``CheckCMS`` thread at boot (TelnetV6.c:1232 / TelnetV6.c:5848) that
validates connectivity to the configured ``CMSSERVER`` on
TCP **8772**.  The destination port is hardcoded
(TelnetV6.c:6113 + 6194); only the *server* is configurable.

Flow with an IP-literal ``CMSSERVER`` (e.g. ``127.0.0.1``):

1. ``CheckCMSThread`` skips DNS, treats the IP as the only address
   (TelnetV6.c:5867-5876), and goes straight to ``CMSCheck``.
2. ``CMSCheck`` calls ``connect()`` to that IP on port 8772
   (TelnetV6.c:6133).  If the connect succeeds, ``CMSOK = TRUE``.
3. ``CMSCheck`` immediately closes the socket — it's purely a
   reachability probe (TelnetV6.c:6135).

This test stands up a fake TCP listener on 127.0.0.1:8772 *before*
booting linbpq and verifies the CheckCMS probe lands.

Limitations / what this *doesn't* cover:

- The actual Winlink CMS handshake protocol — no docs were given
  for it, so we can't fake the server side beyond the connect+close
  reachability probe.  Full handshake coverage would need a Winlink
  CMS server simulator and is flagged in notes/plan.md as still open.
- Cannot run in parallel with another test that wants port 8772 —
  the destination port is hardcoded.  Only one CMS test in the
  suite, kept in this file, so xdist won't double-up.
"""

from __future__ import annotations

import socket
from pathlib import Path
from string import Template

import pytest

from helpers.linbpq_instance import LinbpqInstance


CMS_PORT = 8772  # hardcoded in TelnetV6.c:6113 + 6194


_CMS_CFG = Template(
    """\
SIMPLE=1
NODECALL=N0CALL
NODEALIAS=TEST
LOCATOR=NONE

PORT
 ID=Telnet
 DRIVER=Telnet
 CONFIG
 TCPPORT=$telnet_port
 HTTPPORT=$http_port
 MAXSESSIONS=10
 USER=test,test,N0CALL,,SYSOP
 CMS=1
 CMSCALL=N0CALL
 CMSPASS=password123
 CMSLOC=IO91WJ
 CMSSERVER=127.0.0.1
ENDPORT
"""
)


def _bind_cms_listener() -> socket.socket | None:
    """Try to bind a TCP listener on 127.0.0.1:8772.  Returns the
    listening socket on success, ``None`` if the port is in use."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(("127.0.0.1", CMS_PORT))
    except OSError:
        s.close()
        return None
    s.listen(5)
    s.settimeout(15.0)
    return s


def test_cms_check_probe_connects_to_configured_server(tmp_path: Path):
    """``CheckCMS`` thread connects to ``CMSSERVER:8772`` at boot to
    validate reachability — see TelnetV6.c::CMSCheck (line 6100).
    With ``CMSSERVER=127.0.0.1`` and a TCP listener bound there
    *before* linbpq starts, the probe lands within seconds."""
    listener = _bind_cms_listener()
    if listener is None:
        pytest.skip(
            f"127.0.0.1:{CMS_PORT} is already in use — cannot bind "
            "fake CMS listener"
        )

    try:
        with LinbpqInstance(tmp_path, config_template=_CMS_CFG):
            try:
                conn, addr = listener.accept()
            except socket.timeout:
                pytest.fail(
                    "fake CMS server didn't receive a connect from "
                    f"linbpq's CheckCMS within 15 s on port {CMS_PORT}"
                )
            try:
                # CMSCheck just opens and closes the socket
                # (TelnetV6.c:6135) — no handshake bytes expected.
                assert addr[0] == "127.0.0.1", (
                    f"unexpected source address from linbpq: {addr!r}"
                )
            finally:
                conn.close()
    finally:
        listener.close()
