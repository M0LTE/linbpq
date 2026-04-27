"""Phase 5 — persistence: state written by one boot is loaded by the next.

Public-interface tests only — we don't peek at internal save files.

The NODES table is observable via the ``NODES`` command.  Adding an
entry with ``NODES ADD`` and persisting via ``SAVENODES`` proves the
save side; the same NODES entry being visible after reboot proves
the load side.  No log-grep, no internal-file existence check.

The BBS message-store side: post a message, reboot, ``R <num>`` it
back — the read-back content is the public-interface assertion.
"""

from __future__ import annotations

from pathlib import Path

from string import Template

from helpers.linbpq_instance import LinbpqInstance
from helpers.telnet_client import TelnetClient


# Cfg with an AXIP port + static ROUTE entry installing a neighbour
# at port 2.  ``NODES ADD ... N0NBR 2`` then associates with a real
# neighbour, so SAVENODES / load round-trip preserves the entry.
_PERSIST_CFG = Template(
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
ENDPORT

PORT
 ID=AXIP
 DRIVER=BPQAXIP
 QUALITY=200
 MINQUAL=1
 CONFIG
 UDP $axip_port
 MAP N0NBR 127.0.0.1 UDP 19999
ENDPORT

ROUTES:
N0NBR,200,2
***
"""
)


def test_savenodes_persists_across_reboot(tmp_path: Path):
    """Add a NODES entry, persist with SAVENODES, reboot in the same
    work dir, confirm the entry is back in the NODES table.

    Uses a static ROUTES: neighbour on port 2 so ``NODES ADD`` can
    associate the destination with a real route — that combination
    is what SAVENODES persists and the next boot loads.

    Public-interface only: no log-grep, no BPQNODES.dat existence
    check.  The ``NODES`` command output before vs. after reboot is
    the entire contract.
    """
    # First boot.
    with LinbpqInstance(tmp_path, config_template=_PERSIST_CFG) as first:
        with TelnetClient("127.0.0.1", first.telnet_port) as client:
            client.login("test", "test")
            client.run_command("PASSWORD")

            # Add a sentinel destination on the configured neighbour.
            add = client.run_command("NODES ADD PRSIST:N0XYZ 200 N0NBR 2")
            assert b"Node Added" in add, (
                f"NODES ADD did not confirm: {add!r}"
            )

            populated = client.run_command("NODES")
            assert b"PRSIST" in populated and b"N0XYZ" in populated, (
                f"NODES ADD did not register sentinel: {populated!r}"
            )

            save = client.run_command("SAVENODES")
            assert b"Ok" in save, f"SAVENODES did not return Ok: {save!r}"

    # Second boot in the same directory; new daemon, new ports.
    with LinbpqInstance(tmp_path, config_template=_PERSIST_CFG) as second:
        with TelnetClient("127.0.0.1", second.telnet_port) as client:
            client.login("test", "test")
            after_reboot = client.run_command("NODES")

    assert b"PRSIST" in after_reboot and b"N0XYZ" in after_reboot, (
        f"NODES sentinel did not survive reboot — persistence broken: "
        f"{after_reboot!r}"
    )


def test_bbs_message_persists_across_reboot(tmp_path: Path):
    """A BBS message posted in one instance is readable from a fresh
    boot in the same data directory.

    Locks in the BPQMail message-store contract: messages live in
    ``Mail/`` plus the message-database files, and a clean reboot
    re-indexes them.  A regression in either the writer or the loader
    breaks this test.
    """
    import time

    from helpers.linbpq_instance import MAIL_CONFIG

    # Round 1: enter BBS, post a message, leave, shut down.
    first = LinbpqInstance(
        tmp_path,
        config_template=MAIL_CONFIG,
        extra_args=("mail",),
    )
    with first:
        with TelnetClient("127.0.0.1", first.telnet_port) as client:
            client.login("test", "test")
            client.write_line("BBS")
            client.read_until(b"Please enter your Name", timeout=5)
            client.read_until(b">", timeout=5)
            client.write_line("Tester")
            client.read_until(b"de N0CALL>", timeout=5)

            client.write_line("SP TEST")
            client.read_until(b"Enter Title", timeout=5)
            client.write_line("persistence-subject")
            client.read_until(b"Enter Message Text", timeout=5)
            client.write_line("body-survives-reboot")
            time.sleep(0.5)  # see test_bbs_message_round_trip
            client.write_line("/EX")
            client.read_until(b"Message: 1 Bid:", timeout=10)

    # Round 2: fresh instance, same dir.  Read message 1.
    # Skip internal-storage assertions here — the public-interface
    # read-back below proves both write and load paths.
    second = LinbpqInstance(
        tmp_path,
        config_template=MAIL_CONFIG,
        extra_args=("mail",),
    )
    with second:
        with TelnetClient("127.0.0.1", second.telnet_port) as client:
            client.login("test", "test")
            client.write_line("BBS")
            # Returning user — no name prompt this time.
            client.read_until(b"de N0CALL>", timeout=5)
            client.write_line("R 1")
            response = client.read_until(b"de N0CALL>", timeout=5)
    assert b"Title: persistence-subject" in response, (
        f"title did not survive reboot: {response!r}"
    )
    assert b"body-survives-reboot" in response, (
        f"body did not survive reboot: {response!r}"
    )
