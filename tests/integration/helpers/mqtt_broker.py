"""A minimal MQTT 3.1.1 broker — just enough to record what
linbpq publishes.

linbpq publishes with QoS 0 (fire-and-forget; the default of
``MQTTAsync_message_initializer`` in paho-mqtt-c).  All we need to
do is accept the CONNECT, respond CONNACK, and capture every
PUBLISH packet.  No subscriber-side delivery is required — the
test inspects ``broker.received`` directly.

Single-connection, sufficient for one linbpq instance.
"""

from __future__ import annotations

import socket
import struct
import threading
from contextlib import contextmanager
from dataclasses import dataclass


# Packet types (MSB nybble of fixed header byte 1).
CONNECT = 1
CONNACK = 2
PUBLISH = 3
PINGREQ = 12
PINGRESP = 13
DISCONNECT = 14


@dataclass(frozen=True)
class PublishedMessage:
    topic: str
    payload: bytes


def _read_varint(sock: socket.socket) -> int:
    """Read MQTT remaining-length varint (1..4 bytes)."""
    multiplier = 1
    value = 0
    for _ in range(4):
        b = sock.recv(1)
        if not b:
            raise ConnectionError("connection closed reading varint")
        value += (b[0] & 0x7F) * multiplier
        if not (b[0] & 0x80):
            return value
        multiplier *= 128
    raise ValueError("malformed remaining-length varint")


def _read_exact(sock: socket.socket, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError(f"closed reading {n} bytes (got {len(buf)})")
        buf += chunk
    return bytes(buf)


def _read_str(buf: bytes, offset: int) -> tuple[str, int]:
    """Read MQTT length-prefixed UTF-8 string starting at offset."""
    length = struct.unpack(">H", buf[offset : offset + 2])[0]
    offset += 2
    return buf[offset : offset + length].decode("utf-8"), offset + length


class MqttBroker:
    """Bind to ``127.0.0.1:<auto>``; accept one connection in a
    background thread; capture all PUBLISH packets."""

    def __init__(self) -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(1)
        self.port: int = self._sock.getsockname()[1]
        self.received: list[PublishedMessage] = []
        self._stop = threading.Event()
        self._client_sock: socket.socket | None = None
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        self._sock.settimeout(0.5)
        while not self._stop.is_set():
            try:
                client, _ = self._sock.accept()
            except (socket.timeout, TimeoutError):
                continue
            except OSError:
                return
            self._client_sock = client
            try:
                self._handle(client)
            except (ConnectionError, OSError):
                pass
            finally:
                try:
                    client.close()
                except OSError:
                    pass

    def _handle(self, sock: socket.socket) -> None:
        sock.settimeout(2.0)
        while not self._stop.is_set():
            header = sock.recv(1)
            if not header:
                return
            packet_type = (header[0] >> 4) & 0x0F
            qos = (header[0] >> 1) & 0x03
            remaining = _read_varint(sock)
            body = _read_exact(sock, remaining) if remaining else b""

            if packet_type == CONNECT:
                # Reply with CONNACK (no session, return code 0 = accepted).
                sock.sendall(bytes([0x20, 0x02, 0x00, 0x00]))
            elif packet_type == PUBLISH:
                topic, off = _read_str(body, 0)
                if qos > 0:
                    # Skip 2-byte packet identifier.  Not testing QoS>0
                    # paths here, but keep it parseable.
                    off += 2
                payload = body[off:]
                with self._lock:
                    self.received.append(PublishedMessage(topic, payload))
            elif packet_type == PINGREQ:
                sock.sendall(bytes([0xD0, 0x00]))
            elif packet_type == DISCONNECT:
                return
            # Anything else: ignored.

    def topics(self) -> list[str]:
        with self._lock:
            return [m.topic for m in self.received]

    def messages_matching(self, prefix: str) -> list[PublishedMessage]:
        with self._lock:
            return [m for m in self.received if m.topic.startswith(prefix)]

    def close(self) -> None:
        self._stop.set()
        for s in (self._client_sock, self._sock):
            try:
                if s is not None:
                    s.close()
            except OSError:
                pass
        self._thread.join(timeout=1.0)


@contextmanager
def mqtt_broker():
    broker = MqttBroker()
    try:
        yield broker
    finally:
        broker.close()
