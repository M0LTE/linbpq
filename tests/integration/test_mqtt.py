"""MQTT integration: linbpq publishes its events to a broker.

linbpq is publish-only — there are no ``MQTTAsync_subscribe`` calls
anywhere in the source.  Topics and payload shapes are documented
in ``docs/mqtt-output.md``.

We stand up a minimal recording broker (``helpers.mqtt_broker``)
on a local TCP port, point linbpq at it via cfg, and inspect what
arrives.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from string import Template

from helpers.linbpq_instance import LinbpqInstance
from helpers.mqtt_broker import mqtt_broker
from helpers.pty_kiss_modem import PtyKissModem, kiss_encode


def _encode_call(call: str, ssid: int = 0, last: bool = True) -> bytes:
    p = call.ljust(6).upper().encode()[:6]
    out = bytearray(b << 1 for b in p)
    out.append(0x60 | ((ssid & 0xF) << 1) | (1 if last else 0))
    return bytes(out)


def _ax25_ui(src: str, dest: str, body: bytes) -> bytes:
    return (
        _encode_call(dest, last=False)
        + _encode_call(src, last=True)
        + bytes([0x03, 0xF0])
        + body
    )


def _cfg_with_mqtt(port: int) -> Template:
    """Default-style cfg + MQTT pointing at our broker."""
    return Template(
        f"""\
SIMPLE=1
NODECALL=N0CALL
NODEALIAS=TEST
LOCATOR=NONE
MQTT=1
MQTT_HOST=127.0.0.1
MQTT_PORT={port}
MQTT_USER=test
MQTT_PASS=test

PORT
 ID=Telnet
 DRIVER=Telnet
 CONFIG
 TCPPORT=$telnet_port
 HTTPPORT=$http_port
 MAXSESSIONS=10
 USER=test,test,N0CALL,,SYSOP
ENDPORT
"""
    )


def _cfg_with_mqtt_and_pty(port: int, slave: str) -> Template:
    """As above, plus a PTY-backed KISS port for serial-RX traces."""
    return Template(
        f"""\
SIMPLE=1
NODECALL=N0CALL
NODEALIAS=TEST
LOCATOR=NONE
MQTT=1
MQTT_HOST=127.0.0.1
MQTT_PORT={port}
MQTT_USER=test
MQTT_PASS=test

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
 PORTNUM=2
 ID=KissSerial
 TYPE=ASYNC
 PROTOCOL=KISS
 COMPORT={slave}
 SPEED=9600
ENDPORT
"""
    )


def _wait_for_topic(broker, prefix: str, timeout: float = 5.0):
    """Poll ``broker.received`` until at least one message has a
    topic starting with ``prefix``."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        msgs = broker.messages_matching(prefix)
        if msgs:
            return msgs
        time.sleep(0.1)
    return []


def test_mqtt_publishes_online_status_on_connect(tmp_path: Path):
    """On successful broker connection, linbpq publishes
    ``{"status":"online"}`` to ``PACKETNODE/<NODECALL>``."""
    with mqtt_broker() as broker:
        with LinbpqInstance(tmp_path, config_template=_cfg_with_mqtt(broker.port)):
            msgs = _wait_for_topic(broker, "PACKETNODE/N0CALL", timeout=10)

    assert msgs, f"no PACKETNODE/N0CALL publish; saw topics: {broker.topics()}"
    payload = json.loads(msgs[0].payload.decode("utf-8"))
    assert payload == {"status": "online"}, f"unexpected payload: {payload!r}"


def test_mqtt_publishes_kiss_rx_trace(tmp_path: Path):
    """A UI frame received on a KISS port produces an
    ``ax25/trace/bpqformat/.../rcvd/<port>`` publish whose payload
    JSON has the expected from / to / port keys."""
    with mqtt_broker() as broker, PtyKissModem() as modem:
        cfg = _cfg_with_mqtt_and_pty(broker.port, modem.slave_path)
        with LinbpqInstance(tmp_path, config_template=cfg):
            time.sleep(1.0)  # let MQTT connect first

            ax25 = _ax25_ui("G7TEST", "NODES", b"hello-mqtt")
            modem.write(kiss_encode(ax25))
            time.sleep(1.0)

            msgs = _wait_for_topic(
                broker, "PACKETNODE/ax25/trace/bpqformat/N0CALL/rcvd/2", timeout=5
            )

    assert msgs, (
        f"no rcvd-trace publish on port 2; saw topics: "
        f"{broker.topics()}"
    )
    payload = json.loads(msgs[0].payload.decode("utf-8"))
    assert payload["from"].startswith("G7TEST")
    assert payload["to"].startswith("NODES")
    assert payload["port"] == 2
    assert "timestamp" in payload


def test_mqtt_publishes_raw_kiss_rx(tmp_path: Path):
    """The same UI frame also lands on
    ``PACKETNODE/kiss/<NODECALL>/rcvd/<port>`` as raw bytes (the
    KISS framing as received from the modem)."""
    with mqtt_broker() as broker, PtyKissModem() as modem:
        cfg = _cfg_with_mqtt_and_pty(broker.port, modem.slave_path)
        with LinbpqInstance(tmp_path, config_template=cfg):
            time.sleep(1.0)

            ax25 = _ax25_ui("G7TEST", "NODES", b"hello-raw")
            modem.write(kiss_encode(ax25))
            time.sleep(1.0)

            msgs = _wait_for_topic(
                broker, "PACKETNODE/kiss/N0CALL/rcvd/2", timeout=5
            )

    assert msgs, f"no raw-kiss publish; saw topics: {broker.topics()}"
    # The raw publish is the AX.25 frame as received (with some
    # leading metadata bytes from BPQ's internal MESSAGE struct).
    # The literal body bytes "hello-raw" are present at the tail.
    assert b"hello-raw" in msgs[0].payload, (
        f"body bytes not in raw publish: {msgs[0].payload.hex()}"
    )
