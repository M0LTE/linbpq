"""NET/ROM L4: a resent fragment loses its last 20 bytes (packet-net/dapps#425).

Each test starts one LinBPQ whose only port is KISS over TCP, with
``helpers/l4_repro.py`` as its TNC, as the far NET/ROM node and as an
AGW application on the LinBPQ node. The application writes 256 bytes,
which LinBPQ sends as two INFO frames (236 bytes with More-follows,
then 20), and the far node withholds the L4 ack so LinBPQ has to send
them again from its hold queue:

| Test | Resend path | Fault |
|---|---|---|
| timer_resend_is_the_frame_sent | L4 timer (L4TIMEOUT) | the resent 236-byte frame carries 216 |
| nak_resend_is_the_frame_sent | INFO ACK with NAK | the same |

The same file runs outside pytest against any LinBPQ build:
``python3 tests/integration/helpers/l4_repro.py ./linbpq``.

Each test asserts the correct behaviour, so it fails on a build
without the fork fix in SENDL4MESSAGE (L4Code.c, marked FORK FIX).
"""

from __future__ import annotations

from pathlib import Path

from helpers import l4_repro
from helpers.linbpq_instance import LINBPQ_BIN


def _run(name: str, tmp_path: Path) -> None:
    r = l4_repro.run_scenario(name, LINBPQ_BIN, tmp_path / name)
    assert r.ok, "\n" + r.report()


def test_timer_resend_is_the_frame_sent(tmp_path: Path):
    _run("timer", tmp_path)


def test_nak_resend_is_the_frame_sent(tmp_path: Path):
    _run("nak", tmp_path)
