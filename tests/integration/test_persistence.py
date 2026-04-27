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
