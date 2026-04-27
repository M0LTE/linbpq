"""Phase 5 — persistence: state written by one boot is loaded by the next.

The simplest demonstrable persistence in linbpq is the routing-table
save file ``BPQNODES.dat``.  On a fresh boot the log says
``Route/Node recovery file BPQNODES.dat not found``.  After a sysop
runs ``SAVENODES``, the file is written, and a subsequent boot in the
same working directory loads it (no warning).

This proves that:
1. The save path is deterministic and lives in the working directory.
2. ``SAVENODES`` actually writes the file (i.e. the keyword is wired up).
3. The next boot picks the file up automatically.

Locks in the boundary contract; a refactor that breaks save/load lands
this test red.
"""

from __future__ import annotations

from pathlib import Path

from helpers.linbpq_instance import LinbpqInstance
from helpers.telnet_client import TelnetClient


NOT_FOUND_MSG = "BPQNODES.dat not found"


def _read_log(instance: LinbpqInstance) -> str:
    return instance.stdout_path.read_text(errors="replace")


def test_savenodes_persists_across_reboot(tmp_path: Path):
    # First boot: nothing on disk, the warning should appear.
    with LinbpqInstance(tmp_path) as first:
        log_first = _read_log(first)
        assert NOT_FOUND_MSG in log_first, (
            "first boot should warn about missing BPQNODES.dat; log was:\n"
            f"{log_first[:2000]}"
        )

        # Become sysop and save.
        with TelnetClient("127.0.0.1", first.telnet_port) as client:
            client.login("test", "test")
            client.run_command("PASSWORD")
            response = client.run_command("SAVENODES")
        assert b"Command requires SYSOP" not in response, (
            f"SAVENODES rejected — sysop unlock failed: {response!r}"
        )

    saved = tmp_path / "BPQNODES.dat"
    assert saved.exists(), "SAVENODES did not write BPQNODES.dat"
    # An empty file is fine here — with no inbound NET/ROM frames the
    # routing table is empty.  What matters is that the file was created
    # and that the next boot loads it (asserted below).

    # Second boot in the same directory: the warning should NOT appear.
    # Note: ``LinbpqInstance(tmp_path)`` reuses the same dir.  New
    # instance gets new ports; that's fine — we're testing data-dir
    # persistence, not network state.
    with LinbpqInstance(tmp_path) as second:
        log_second = _read_log(second)
    assert NOT_FOUND_MSG not in log_second, (
        "second boot still warned about missing BPQNODES.dat — "
        "load path broken; log was:\n"
        f"{log_second[:2000]}"
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

    # The Mail/ directory and the message databases should have been
    # written by the time first.stop() returns.
    mail_dir = tmp_path / "Mail"
    assert mail_dir.is_dir(), f"Mail dir missing under {tmp_path}"
    msg_files = list(mail_dir.glob("m_*.mes"))
    assert msg_files, f"no .mes files written under {mail_dir}"

    # Round 2: fresh instance, same dir.  Read message 1.
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
