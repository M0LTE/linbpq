"""Minimal AGWPE-protocol client for integration tests.

AGW frames are a 36-byte fixed header followed by ``DataLength`` bytes of
payload.  The header layout (see AGWAPI.c struct AGWHeader) is:

    offset  size  field
    ------  ----  -----
    0       1     Port
    1       3     filler
    4       1     DataKind   (single ASCII character — the command)
    5       1     filler
    6       1     PID
    7       1     filler
    8       10    callfrom (NUL-padded)
    18      10    callto   (NUL-padded)
    28      4     DataLength (little-endian uint32)
    32      4     reserved

This helper does only what tests need: assemble a request, send it, read
exactly one reply frame back.
"""

from __future__ import annotations

import socket
import struct
import time
from dataclasses import dataclass

AGW_HEADER_SIZE = 36
AGW_HEADER_FMT = "<B 3x c B B x 10s 10s I 4x"
# B=Port, 3x=filler1, c=DataKind, B=filler2, B=PID, x=filler3,
# 10s=callfrom, 10s=callto, I=DataLength, 4x=reserved
assert struct.calcsize(AGW_HEADER_FMT) == AGW_HEADER_SIZE


@dataclass
class AgwFrame:
    port: int
    data_kind: bytes  # one byte
    pid: int
    callfrom: bytes
    callto: bytes
    data: bytes

    @classmethod
    def from_header_and_data(cls, header: bytes, data: bytes) -> "AgwFrame":
        port, kind, _filler2, pid, callfrom, callto, _length = struct.unpack(
            AGW_HEADER_FMT, header
        )
        return cls(
            port=port,
            data_kind=kind,
            pid=pid,
            callfrom=callfrom.rstrip(b"\x00"),
            callto=callto.rstrip(b"\x00"),
            data=data,
        )

    def pack(self) -> bytes:
        header = struct.pack(
            AGW_HEADER_FMT,
            self.port,
            self.data_kind,
            0,
            self.pid,
            self.callfrom.ljust(10, b"\x00"),
            self.callto.ljust(10, b"\x00"),
            len(self.data),
        )
        return header + self.data


class AgwClient:
    def __init__(self, host: str, port: int, timeout: float = 3.0):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.sock.settimeout(timeout)

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass

    def __enter__(self) -> "AgwClient":
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    def send(self, frame: AgwFrame) -> None:
        self.sock.sendall(frame.pack())

    def recv(self) -> AgwFrame:
        header = self._recv_exact(AGW_HEADER_SIZE)
        (_port, _kind, _f2, _pid, _cf, _ct, length) = struct.unpack(
            AGW_HEADER_FMT, header
        )
        data = self._recv_exact(length) if length else b""
        return AgwFrame.from_header_and_data(header, data)

    def _recv_exact(self, n: int) -> bytes:
        buf = bytearray()
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise ConnectionError(
                    f"AGW connection closed mid-frame ({len(buf)}/{n})"
                )
            buf += chunk
        return bytes(buf)


class AgwSession:
    """Higher-level wrapper around ``AgwClient`` that owns the
    register / connect / wait / send / drain patterns repeated
    across the integration suite.

    Each method speaks one AGW frame kind.  Construct via
    ``AgwSession.connect(host, port)`` (which builds the underlying
    ``AgwClient``) or wrap an existing client with
    ``AgwSession(client)``.

    Use as a context manager — ``__exit__`` closes the underlying
    socket.
    """

    def __init__(self, client: AgwClient) -> None:
        self.client = client

    @classmethod
    def connect(cls, host: str, port: int, timeout: float = 15.0) -> "AgwSession":
        return cls(AgwClient(host, port, timeout=timeout))

    def __enter__(self) -> "AgwSession":
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    def close(self) -> None:
        self.client.close()

    @property
    def sock(self) -> socket.socket:
        return self.client.sock

    def send(self, frame: AgwFrame) -> None:
        self.client.send(frame)

    def recv(self) -> AgwFrame:
        return self.client.recv()

    # ── AGW frame kinds ──────────────────────────────────────────

    def register(self, callsign: str) -> None:
        """Send AGW ``X`` (register callsign), assert positive ack."""
        self.client.send(
            AgwFrame(
                port=0,
                data_kind=b"X",
                pid=0,
                callfrom=callsign.encode("ascii"),
                callto=b"",
                data=b"",
            )
        )
        reply = self.client.recv()
        if reply.data_kind != b"X" or reply.data != b"\x01":
            raise AssertionError(
                f"AGW register {callsign!r} failed: {reply!r}"
            )

    def connect_call(
        self, port_index: int, callfrom: str, callto: str
    ) -> None:
        """Send AGW ``C`` (initiate connect).  No in-line ack — caller
        waits for the confirm with ``wait_for(b"C")``.
        """
        self.client.send(
            AgwFrame(
                port=port_index,
                data_kind=b"C",
                pid=0,
                callfrom=callfrom.encode("ascii"),
                callto=callto.encode("ascii"),
                data=b"",
            )
        )

    def send_data(
        self,
        port_index: int,
        callfrom: str,
        callto: str,
        data: bytes,
    ) -> None:
        """Send AGW ``D`` (connected data) frame."""
        self.client.send(
            AgwFrame(
                port=port_index,
                data_kind=b"D",
                pid=0xF0,
                callfrom=callfrom.encode("ascii"),
                callto=callto.encode("ascii"),
                data=data,
            )
        )

    # ── Receive helpers ──────────────────────────────────────────

    def wait_for(self, kind: bytes, timeout: float = 10.0) -> AgwFrame:
        """Pump recv until a frame with matching ``data_kind`` arrives.
        Raises ``RuntimeError`` if a ``d`` (disconnect) lands first,
        ``TimeoutError`` on deadline.
        """
        deadline = time.monotonic() + timeout
        prev = self.sock.gettimeout()
        self.sock.settimeout(0.5)
        try:
            while time.monotonic() < deadline:
                try:
                    frame = self.client.recv()
                except (TimeoutError, socket.timeout):
                    continue
                if frame.data_kind == kind:
                    return frame
                if frame.data_kind == b"d":
                    raise RuntimeError(
                        f"got disconnect while waiting for {kind!r}: {frame!r}"
                    )
            raise TimeoutError(f"no AGW {kind!r} frame within {timeout}s")
        finally:
            self.sock.settimeout(prev)

    def drain_data(
        self,
        expected_min: int = 0,
        timeout: float = 8.0,
        trailing: float = 1.0,
    ) -> bytes:
        """Read frames until at least ``expected_min`` bytes of ``D``
        data have accumulated or ``timeout`` elapses, then briefly
        drain any trailing data.  Ignores non-``D`` frames except
        ``d`` which short-circuits the wait.  Returns the
        concatenated payload.
        """
        deadline = time.monotonic() + timeout
        prev = self.sock.gettimeout()
        self.sock.settimeout(0.5)
        payload = b""
        try:
            while (
                time.monotonic() < deadline and len(payload) < expected_min
            ):
                try:
                    frame = self.client.recv()
                except (TimeoutError, socket.timeout):
                    continue
                if frame.data_kind == b"D":
                    payload += frame.data
                elif frame.data_kind == b"d":
                    break
            deadline2 = time.monotonic() + trailing
            while time.monotonic() < deadline2:
                try:
                    frame = self.client.recv()
                except (TimeoutError, socket.timeout):
                    break
                if frame.data_kind == b"D":
                    payload += frame.data
            return payload
        finally:
            self.sock.settimeout(prev)


def request_version(host: str, port: int, timeout: float = 3.0) -> tuple[int, int]:
    """Send an 'R' frame (request AGW version), return (major, minor)."""
    with AgwClient(host, port, timeout=timeout) as client:
        client.send(
            AgwFrame(
                port=0,
                data_kind=b"R",
                pid=0,
                callfrom=b"",
                callto=b"",
                data=b"",
            )
        )
        reply = client.recv()
    if reply.data_kind != b"R":
        raise AssertionError(
            f"expected 'R' reply, got {reply.data_kind!r}"
        )
    if len(reply.data) != 8:
        raise AssertionError(
            f"expected 8-byte version payload, got {len(reply.data)} bytes"
        )
    major, minor = struct.unpack("<II", reply.data)
    return major, minor
