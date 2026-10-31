"""AX.25 link-layer sequence faults found in packet-net/dapps#425.

Each test starts one LinBPQ whose only port is KISS over TCP, with
``helpers/l2_repro.py`` as its TNC and as the far end of the link, and
plays an exact frame sequence at it:

| Test | Fault | AX.25 2.3 draft |
|---|---|---|
| repeated_i_frames_are_discarded | repeats kept as future frames: SREJ for a frame never sent, then stale frames delivered as new | 4.4.2, 6.4.4.1, 6.4.4.2 |
| invalid_nr_resets_the_link | one bad N(R) and the link goes silent until it retries out (FRMRHACK) | 4.3.3.9, 6.5, figure C4.7 |
| frames_without_new_ack_keep_the_link | "Too many repeats of same I frame" disconnects a healthy link | 6.4.6, 6.4.11 |

The same file runs outside pytest against any LinBPQ build:
``python3 tests/integration/helpers/l2_repro.py ./linbpq``.

Each test asserts the correct behaviour, so it fails on a build
without the matching fork fix in L2Code.c (marked FORK FIX).
"""

from __future__ import annotations

from pathlib import Path

from helpers import l2_repro
from helpers.linbpq_instance import LINBPQ_BIN


def _run(name: str, tmp_path: Path) -> None:
    r = l2_repro.run_scenario(name, LINBPQ_BIN, tmp_path / name)
    assert r.ok, "\n" + r.report()


def test_repeated_i_frames_are_discarded(tmp_path: Path):
    _run("dup", tmp_path)


def test_invalid_nr_resets_the_link(tmp_path: Path):
    _run("badnr", tmp_path)


def test_frames_without_new_ack_keep_the_link(tmp_path: Path):
    _run("counter", tmp_path)


def test_peer_stuck_on_one_srej_is_disconnected(tmp_path: Path):
    _run("srejloop", tmp_path)
