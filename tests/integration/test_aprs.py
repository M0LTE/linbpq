"""APRS subsystem coverage (gap-analysis closeout).

GB7RDG's production cfg uses an ``APRSDIGI`` ... ``***`` block with
position, symbol, IS-uplink details and an OBJECT beacon.  Up to
this batch we only had a "no APRS configured" canary
(``APRS ?`` lists subcommands).  Now: lock in the
APRSDIGI-configured behaviour.

Tests stand the daemon up with ``ISHost=127.0.0.1`` pointing at a
local TCP listener, so linbpq's outbound APRS-IS connect is
observable.  We don't drive the full APRS-IS login protocol
(``user N0CALL pass NNNNN``), just verify linbpq dials out.
"""

from __future__ import annotations

import socket
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from string import Template

from helpers.linbpq_instance import LinbpqInstance
from helpers.telnet_client import TelnetClient


@contextmanager
def aprs_is_listener():
    """Tiny TCP listener that records what linbpq sends after it
    connects.  Runs the accept loop on a background thread; the
    test inspects ``server.received`` after a short wait."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    port = sock.getsockname()[1]

    state = {"received": b"", "connected": False}
    stop = threading.Event()

    def run():
        sock.settimeout(0.5)
        while not stop.is_set():
            try:
                client, _ = sock.accept()
            except (socket.timeout, TimeoutError):
                continue
            except OSError:
                return
            state["connected"] = True
            client.settimeout(2.0)
            # Read for a couple of seconds — APRS-IS clients send
            # their login line on connect.
            deadline = time.monotonic() + 3.0
            while time.monotonic() < deadline:
                try:
                    chunk = client.recv(4096)
                except (TimeoutError, socket.timeout):
                    continue
                if not chunk:
                    break
                state["received"] += chunk
            try:
                client.close()
            except OSError:
                pass
            return

    t = threading.Thread(target=run, daemon=True)
    t.start()
    try:
        yield port, state
    finally:
        stop.set()
        try:
            sock.close()
        except OSError:
            pass
        t.join(timeout=1.0)


def _aprs_cfg(is_port: int) -> Template:
    return Template(
        f"""\
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
ENDPORT

APRSDIGI
LAT=5126.83N
LON=00101.62W
StatusMsg=Test APRS status
Symbol=B
Symset=/
ISHost=127.0.0.1
ISPort={is_port}
ISPasscode=12345
BeaconInterval=60
***
"""
    )


def test_aprsdigi_block_parses_and_status_reports_igate(tmp_path: Path):
    """Configuring an APRSDIGI block enables the iGate; the
    ``APRS STATUS`` command reports ``IGate Enabled but not
    connected`` when the IS host can't be reached (test pointing at
    127.0.0.1 with a closed port — port not bound during test)."""
    cfg = _aprs_cfg(1)  # port 1 — almost certainly nothing listening
    with LinbpqInstance(tmp_path, config_template=cfg) as linbpq:
        with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
            client.login("test", "test")
            response = client.run_command("APRS STATUS")
    assert b"IGate Enabled" in response, (
        f"APRS STATUS missing IGate state: {response!r}"
    )


def test_aprs_sent_and_msgs_return_table_headers(tmp_path: Path):
    """``APRS SENT`` and ``APRS MSGS`` each return a column header
    line; locks in the column layout in case it drifts."""
    cfg = _aprs_cfg(1)
    with LinbpqInstance(tmp_path, config_template=cfg) as linbpq:
        with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
            client.login("test", "test")
            sent = client.run_command("APRS SENT")
            msgs = client.run_command("APRS MSGS")

    assert b"Time" in sent and b"Calls" in sent and b"Seq" in sent, (
        f"APRS SENT header missing columns: {sent!r}"
    )
    assert b"Time" in msgs and b"Calls" in msgs, (
        f"APRS MSGS header missing columns: {msgs!r}"
    )


def test_aprs_beacon_requires_sysop_then_succeeds(tmp_path: Path):
    """``APRS BEACON`` is sysop-gated; after PASSWORD it returns
    ``Beacons requested``."""
    cfg = _aprs_cfg(1)
    with LinbpqInstance(tmp_path, config_template=cfg) as linbpq:
        with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
            client.login("test", "test")
            gated = client.run_command("APRS BEACON")
            assert b"Command requires SYSOP status" in gated, (
                f"APRS BEACON not gated: {gated!r}"
            )

            client.run_command("PASSWORD")
            unlocked = client.run_command("APRS BEACON")

    assert b"Beacons requested" in unlocked, (
        f"APRS BEACON didn't confirm: {unlocked!r}"
    )


def test_aprs_dials_out_to_is_host(tmp_path: Path):
    """When ``APRSDIGI`` declares ``ISHost`` / ``ISPort`` /
    ``ISPasscode``, linbpq attempts an outbound TCP connection to
    that host:port to upload to APRS-IS.  A local TCP listener
    standing in as the IS server accepts within a few seconds."""
    with aprs_is_listener() as (is_port, state):
        cfg = _aprs_cfg(is_port)
        with LinbpqInstance(tmp_path, config_template=cfg):
            # Give linbpq up to 5s to dial out.
            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline and not state["connected"]:
                time.sleep(0.1)

    assert state["connected"], (
        "linbpq did not connect to the configured ISHost"
    )
    # Once connected, APRS-IS clients send a login line beginning with
    # 'user '.  Lock that in if we received any data.
    if state["received"]:
        assert state["received"].startswith(b"user "), (
            f"unexpected APRS-IS login: {state['received']!r}"
        )
