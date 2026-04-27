"""Fake FBB-protocol BBS partner for testing linbpq's mail forwarding.

Connects via TCP (telnet -> BBS application) into a configured
linbpq instance, exchanges SIDs, and drives the
[FBB forwarding protocol](https://github.com/packethacking/ax25spec/blob/main/doc/fbb-forwarding-protocol.md).

Capabilities:

- Build a SID with arbitrary capability flags (``F`` for FBB,
  ``B``/``B1``/``B2`` for compressed modes, ``H`` hierarchical,
  ``M`` MID, ``$`` end-of-flags) — used to drive linbpq's per-flag
  code paths.
- Read linbpq's SID and parse capability flags out.
- Drive proposal-response rounds: read ``FA``/``FB``/``FC``/``F>``,
  send ``FS +-=`` etc., capture the message body up to ``\\x1A``
  terminator, then optionally counter-propose.
- Handle the empty-queue cases: receive ``FF`` (no more from peer)
  and respond ``FQ`` to terminate.
- Send our own proposal block from a list of fake messages.

ASCII / B1 / B2 mode handling: the message-body reader supports
both ASCII (read until ``\\x1A``) and B1/B2 binary blocks
(``\\x01`` SOH header + ``\\x02`` STX data blocks + ``\\x04`` EOT
checksum) — far end mode is determined by the SID exchange and
proposal type.

This helper is the test side; it doesn't *implement* compression
(no LZHUF) — it just captures byte streams and asserts on framing.
"""

from __future__ import annotations

import re
import socket
import time
from contextlib import contextmanager
from dataclasses import dataclass, field


SOH = 0x01
STX = 0x02
EOT = 0x04
SUB = 0x1A  # Ctrl-Z

# Default partner SID — claims B1/B2/F so linbpq enables compressed-mode
# proposals if our forwarding partner cfg also allows them.
DEFAULT_PARTNER_SID = b"[FBB-7.10-B12FHM$]\r"


@dataclass
class ProposalRound:
    """Captured state from one round of partner-driven proposals."""

    sid: bytes = b""
    proposals: list[bytes] = field(default_factory=list)
    block_terminator: bytes = b""  # the F> XX line
    fs_response: bytes = b""  # we send this back
    messages: list[bytes] = field(default_factory=list)
    final_command: bytes = b""  # FF or FQ that ends the round


class FBBPartner:
    """One-shot connection to linbpq's BBS application as a forwarding peer."""

    def __init__(
        self,
        host: str,
        port: int,
        *,
        username: str,
        password: str,
        sid: bytes = DEFAULT_PARTNER_SID,
        timeout: float = 10.0,
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.sid_to_send = sid
        self.timeout = timeout

        self._sock: socket.socket | None = None
        self._buf = bytearray()

    # -- connection lifecycle -----------------------------------------

    def __enter__(self) -> "FBBPartner":
        self._sock = socket.create_connection(
            (self.host, self.port), timeout=self.timeout
        )
        self._sock.settimeout(0.5)
        return self

    def __exit__(self, *_exc) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass

    # -- raw I/O ------------------------------------------------------

    def _read_more(self, max_seconds: float = 2.0) -> bytes:
        """Block-read until something arrives or we time out."""
        assert self._sock is not None
        deadline = time.monotonic() + max_seconds
        while time.monotonic() < deadline:
            self._sock.settimeout(min(0.4, max(0.05, deadline - time.monotonic())))
            try:
                chunk = self._sock.recv(4096)
            except (TimeoutError, socket.timeout):
                continue
            if chunk == b"":
                raise ConnectionResetError("partner socket closed")
            self._buf.extend(chunk)
            return chunk
        return b""

    def read_until(self, marker: bytes, timeout: float = 5.0) -> bytes:
        """Read until ``marker`` appears in the buffer; return everything
        up to and including the marker, leaving the rest in the buffer."""
        deadline = time.monotonic() + timeout
        while marker not in self._buf:
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"timed out waiting for {marker!r}; got {bytes(self._buf)!r}"
                )
            self._read_more(max_seconds=deadline - time.monotonic())
        idx = self._buf.index(marker) + len(marker)
        out = bytes(self._buf[:idx])
        del self._buf[:idx]
        return out

    def read_bytes(self, n: int, timeout: float = 5.0) -> bytes:
        """Read exactly ``n`` bytes."""
        deadline = time.monotonic() + timeout
        while len(self._buf) < n:
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"timed out waiting for {n} bytes; got {len(self._buf)}: {bytes(self._buf)!r}"
                )
            self._read_more(max_seconds=deadline - time.monotonic())
        out = bytes(self._buf[:n])
        del self._buf[:n]
        return out

    def write(self, data: bytes) -> None:
        assert self._sock is not None
        self._sock.sendall(data)

    def send_line(self, line: bytes) -> None:
        """Send one CRLF-terminated line.

        Empirically, linbpq's BBS line-input lexer needs ``\\r\\n``
        (or ``\\n`` alone) to delimit incoming commands cleanly when
        multiple lines are written back-to-back.  The FBB spec allows
        bare CR; in practice, linbpq's BPQMail demultiplexes
        rapidly-arrived bare-CR-separated lines as one buffer and
        misparses them.  Use ``\\r\\n`` for reliable framing.
        """
        line = line.rstrip(b"\r\n") + b"\r\n"
        self.write(line)

    # -- BBS login ----------------------------------------------------

    def login_to_bbs(self, bbs_call: str = "N0AAA") -> bytes:
        """Run the linbpq telnet login and enter the BBS application.

        After the partner-BBS user record's F_BBS flag is honoured,
        BPQMail sends ``[BPQ-...]\\r`` (the SID) followed by a welcome
        message and the ``de <call>>`` node prompt.  We read up to and
        including the prompt so the buffer is clean for SID exchange,
        and return the SID line for inspection.
        """
        # username/password prompts
        self.read_until(b"user:", timeout=5)
        self.write(self.username.encode("ascii") + b"\r")
        self.read_until(b"password:", timeout=5)
        self.write(self.password.encode("ascii") + b"\r")
        # Read the node-level "Welcome to..." banner up to the node prompt.
        self.read_until(b"\n", timeout=5)
        # Enter BBS application.
        self.send_line(b"BBS")
        # linbpq sends its SID then the BBS welcome message and prompt.
        # Read up to and including the BBS prompt so the SID is in the
        # consumed bytes; then extract it.
        prompt = f"de {bbs_call}>".encode()
        consumed = self.read_until(prompt, timeout=8)
        m = re.search(rb"\[[^\]]+\]", consumed)
        if not m:
            raise RuntimeError(f"no SID in banner: {consumed!r}")
        return m.group(0)

    def send_sid(self, sid: bytes | None = None) -> None:
        """Send our SID after reading linbpq's.  CRLF-terminated."""
        s = sid if sid is not None else self.sid_to_send
        self.write(s.rstrip(b"\r\n") + b"\r\n")

    # -- protocol round 1: linbpq proposes, we accept/reject ----------

    def read_one_command(self, timeout: float = 5.0) -> bytes:
        """Read one CR-terminated FBB command line, skipping over empty
        lines (linbpq sometimes emits stray CR/LF between BBS welcome
        text and FBB-mode commands).  Consumes the trailing ``\\n`` if
        present so the buffer doesn't leave orphan LFs that confuse
        the next binary-mode read."""
        deadline = time.monotonic() + timeout
        while True:
            line = self.read_until(b"\r", timeout=max(0.1, deadline - time.monotonic()))
            # Pull trailing LF if present, so a B1/B2 binary read
            # following this command doesn't see the leftover \n.
            if self._buf[:1] == b"\n":
                del self._buf[:1]
            stripped = line.lstrip(b"\r\n")
            if stripped:
                return stripped

    def read_proposal_block(self, timeout: float = 10.0) -> tuple[list[bytes], bytes]:
        """Read FA/FB/FC proposal lines until F>; return ``(props, terminator)``.

        If linbpq has nothing to send, the first line will be ``FF\\r``
        or ``FQ\\r`` instead of a proposal — those are returned as a
        single-element ``[FF\\r]`` / ``[FQ\\r]`` list with empty terminator.
        """
        proposals: list[bytes] = []
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            line = self.read_one_command(timeout=deadline - time.monotonic())
            if line[:2] in (b"FA", b"FB", b"FC"):
                proposals.append(line)
            elif line[:2] == b"F>":
                return proposals, line
            elif line[:2] in (b"FF", b"FQ"):
                return [line], b""
            elif line.startswith(b";"):
                # Comment line (e.g. ; MSGTYPES) — just continue.
                continue
            else:
                raise RuntimeError(
                    f"unexpected line in proposal block: {line!r}"
                )
        raise TimeoutError(
            f"timed out reading proposal block; got: {proposals!r}"
        )

    def send_fs_response(self, codes: bytes) -> None:
        """Reply to a proposal block with ``FS <codes>``."""
        self.send_line(b"FS " + codes)

    def read_ascii_message(self, timeout: float = 10.0) -> bytes:
        """Read an ASCII-mode message body up to the ``\\x1A`` terminator."""
        return self.read_until(bytes([SUB]), timeout=timeout)

    def read_b1_message(self, timeout: float = 10.0) -> bytes:
        """Read one B1/B2 binary message: SOH header + STX blocks + EOT.

        Returns the full byte stream verbatim.
        """
        out = bytearray()
        deadline = time.monotonic() + timeout

        # SOH header
        soh = self.read_bytes(1, timeout=deadline - time.monotonic())
        if soh != bytes([SOH]):
            raise RuntimeError(f"expected SOH, got {soh!r}")
        out += soh
        length_b = self.read_bytes(1, timeout=deadline - time.monotonic())
        out += length_b
        # SOH-header body: <length> bytes of (title NUL offset NUL)
        body = self.read_bytes(length_b[0], timeout=deadline - time.monotonic())
        out += body

        # Then STX <size> <data> blocks until EOT <checksum>
        while True:
            ctrl = self.read_bytes(1, timeout=deadline - time.monotonic())
            out += ctrl
            if ctrl == bytes([STX]):
                size_b = self.read_bytes(1, timeout=deadline - time.monotonic())
                out += size_b
                size = size_b[0] if size_b[0] != 0 else 256
                data = self.read_bytes(size, timeout=deadline - time.monotonic())
                out += data
            elif ctrl == bytes([EOT]):
                csum = self.read_bytes(1, timeout=deadline - time.monotonic())
                out += csum
                return bytes(out)
            else:
                raise RuntimeError(
                    f"expected STX or EOT, got 0x{ctrl[0]:02x}"
                )

    # -- partner-side: send our own proposals -------------------------

    def send_proposal_block(self, proposals: list[bytes]) -> None:
        """Send our own proposal lines, then ``F> <checksum>``.

        Per FBB spec §5.2 / §6.2, the checksum sums all bytes of the
        proposal lines (including the CR terminators) and the F>'s
        hex digit is the negated 8-bit sum.
        """
        checksum = 0
        for prop in proposals:
            prop = prop.rstrip(b"\r\n") + b"\r"
            for b in prop:
                checksum = (checksum + b) & 0xFF
            # Send each prop with CRLF for reliable line framing.
            self.write(prop + b"\n")
        checksum = (-checksum) & 0xFF
        self.send_line(f"F> {checksum:02X}".encode("ascii"))

    def send_ff(self) -> None:
        """No-more-messages."""
        self.send_line(b"FF")

    def send_fq(self) -> None:
        """Disconnect."""
        self.send_line(b"FQ")


@contextmanager
def fbb_partner(host: str, port: int, **kwargs):
    p = FBBPartner(host, port, **kwargs)
    with p:
        yield p
