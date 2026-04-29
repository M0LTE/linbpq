"""Doc cfg-snippet boot check.

Iterates every fenced ``ini`` block under ``docs/**/*.md``,
classifies each, wraps fragments in a harness that boots cleanly
on its own, spawns a real linbpq with each, and asserts the
parser:

- prints ``Conversion (probably) successful``
- does not print ``not recognised - Ignored:`` for any keyword
- does not print ``Conversion failed`` or ``Bad config record``
- does not hit the missing-NODECALL / missing-LOCATOR errors

Catches docs that drift from the parser when keywords are
renamed, removed, or repurposed upstream.  Complements the
static citation gate in ``tests/playwright/test_repo_audits.py``
(which covers the source-line side).

Skipped blocks:

- Blocks containing illustrative placeholders (``...``,
  ``<your-call>``, ``driver-specific lines``) — pedagogical
  rather than bootable.
- Blocks that are systemd unit / socket files (``[Unit]`` /
  ``[Socket]`` headers), which use INI syntax but aren't BPQ
  cfg.

The id format is ``<docs-relative-path>:<line>`` so a failure
points straight at the offending fenced block.
"""

from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path

import pytest

from helpers.linbpq_instance import LINBPQ_BIN, pick_free_port

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DOCS_ROOT = _REPO_ROOT / "docs"

_INI_FENCE = re.compile(r"^```ini\n(.*?)^```$", re.MULTILINE | re.DOTALL)

# Pedagogical placeholders — the block isn't meant to parse as-is.
_PLACEHOLDERS = (
    "...",
    "<insert",
    "<your",
    "<call",
    "<peer",
    "<port>",
    "<callsign>",
    "driver-specific lines",
    "other PORT keywords",
)

# Lines that mark a systemd unit / desktop file rather than BPQ cfg.
_SYSTEMD_HEADERS = re.compile(
    r"^\[(Unit|Service|Socket|Install|Desktop Entry)\]", re.MULTILINE
)


def _is_placeholder(block: str) -> bool:
    lower = block.lower()
    return any(p.lower() in lower for p in _PLACEHOLDERS)


def _is_systemd(block: str) -> bool:
    return bool(_SYSTEMD_HEADERS.search(block))


def _is_full_cfg(block: str) -> bool:
    """A block is bootable on its own iff it sets NODECALL."""
    return any(
        line.strip().upper().startswith("NODECALL=")
        for line in block.splitlines()
    )


def _harness(telnet_port: int, http_port: int, axip_port: int) -> str:
    """Boot harness for fragment-style doc blocks.

    Two PORT blocks (Telnet on port 1, BPQAXIP loopback on port 2)
    so fragments that reference ``APRSPath 2=``, ``Digimap 2=``,
    ``QUALITY 2 ...`` etc. find a port to bind to.  The AXIP socket
    is bound to a free port pair on loopback so it's a no-op at
    runtime.
    """
    return (
        "SIMPLE=1\n"
        "NODECALL=N0CALL\n"
        "NODEALIAS=TEST\n"
        "LOCATOR=NONE\n"
        "\n"
        "PORT\n"
        " ID=Telnet\n"
        " DRIVER=Telnet\n"
        " CONFIG\n"
        f" TCPPORT={telnet_port}\n"
        f" HTTPPORT={http_port}\n"
        " MAXSESSIONS=10\n"
        " USER=test,test,N0CALL,,SYSOP\n"
        "ENDPORT\n"
        "\n"
        "PORT\n"
        " ID=AXIP\n"
        " DRIVER=BPQAXIP\n"
        " CONFIG\n"
        f" UDP {axip_port}\n"
        "ENDPORT\n"
        "\n"
    )


def _normalise_ports(
    block: str, telnet_port: int, http_port: int, agw_port: int
) -> str:
    """Replace hardcoded port values in a doc block with the per-test
    free ports so parallel tests don't fight for the same socket.
    The test target is keyword acceptance, not the specific port
    values, so substitution doesn't affect coverage."""
    block = re.sub(r"(TCPPORT\s*=\s*)\d+", rf"\g<1>{telnet_port}", block)
    block = re.sub(r"(HTTPPORT\s*=\s*)\d+", rf"\g<1>{http_port}", block)
    block = re.sub(r"(AGWPORT\s*=\s*)\d+", rf"\g<1>{agw_port}", block)
    return block


def _discover_blocks() -> list[tuple[Path, int, str]]:
    out: list[tuple[Path, int, str]] = []
    for md in sorted(_DOCS_ROOT.rglob("*.md")):
        text = md.read_text()
        for m in _INI_FENCE.finditer(text):
            line = text[: m.start()].count("\n") + 1
            out.append((md, line, m.group(1)))
    return out


_BLOCKS = _discover_blocks()


def _id(item: tuple[Path, int, str]) -> str:
    md, line, _ = item
    return f"{md.relative_to(_DOCS_ROOT).as_posix()}:{line}"


def _spawn_and_check(cfg_text: str, tmp_path: Path) -> bytes:
    """Boot linbpq with ``cfg_text``, capture stdout until the parser
    has reported its outcome, then terminate.  Returns the captured
    stdout for assertions.
    """
    cfg_path = tmp_path / "bpq32.cfg"
    cfg_path.write_text(cfg_text)
    log_path = tmp_path / "linbpq.stdout.log"

    proc = subprocess.Popen(
        [LINBPQ_BIN],
        cwd=tmp_path,
        stdout=log_path.open("wb"),
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 10.0
        terminal_markers = (
            b"Conversion (probably) successful",
            b"Conversion failed",
            b"Missing NODECALL",
            b"Please enter a LOCATOR",
            b"No valid radio ports defined",
        )
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                break
            text = log_path.read_bytes()
            if any(marker in text for marker in terminal_markers):
                break
            time.sleep(0.2)
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
    return log_path.read_bytes()


_BLOCK_IDS = [_id(b) for b in _BLOCKS]


@pytest.mark.parametrize("md,line_no,block", _BLOCKS, ids=_BLOCK_IDS)
def test_doc_cfg_snippet_parses(
    md: Path, line_no: int, block: str, tmp_path: Path
) -> None:
    if _is_placeholder(block):
        pytest.skip("illustrative placeholder block")
    if _is_systemd(block):
        pytest.skip("systemd unit file, not BPQ cfg")

    telnet_port = pick_free_port()
    http_port = pick_free_port()
    agw_port = pick_free_port()
    axip_port = pick_free_port()
    block_norm = _normalise_ports(block, telnet_port, http_port, agw_port)

    if _is_full_cfg(block_norm):
        cfg = block_norm
    else:
        cfg = _harness(telnet_port, http_port, axip_port) + block_norm

    log = _spawn_and_check(cfg, tmp_path)

    rel = md.relative_to(_REPO_ROOT)
    failure_signals = [
        b"Conversion failed",
        b"not recognised - Ignored:",
        b"Bad config record",
        b"Missing NODECALL",
        b"Please enter a LOCATOR",
    ]
    for signal in failure_signals:
        assert signal not in log, (
            f"{rel}:{line_no} cfg block fails to parse cleanly.\n"
            f"Signal: {signal!r}\n"
            f"--- block ---\n{block}\n"
            f"--- generated cfg ---\n{cfg}\n"
            f"--- linbpq stdout ---\n{log[:2000].decode(errors='replace')}"
        )
    assert b"Conversion (probably) successful" in log, (
        f"{rel}:{line_no} did not reach 'Conversion successful'.\n"
        f"--- block ---\n{block}\n"
        f"--- generated cfg ---\n{cfg}\n"
        f"--- linbpq stdout ---\n{log[:2000].decode(errors='replace')}"
    )
