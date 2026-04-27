# LinBPQ MQTT output

> Empirical reference compiled from `mqtt.c` and the call sites that
> invoke each publish function.  Cross-checked by the integration
> tests in `tests/integration/test_mqtt.py`.  AI-assisted; verify
> against the source if anything looks off.

LinBPQ's MQTT integration is **publish-only** — there are no
`MQTTAsync_subscribe` calls anywhere in the source.  Configure with:

```
MQTT=1
MQTT_HOST=<broker-host>
MQTT_PORT=1883
MQTT_USER=<user>
MQTT_PASS=<pass>
```

All topics are prefixed with `PACKETNODE/`.  Where a topic includes
a callsign, it is `NODECALLLOPPED` — the configured `NODECALL` with
any SSID stripped.

## Topics at a glance

| Topic | Payload | Fired from |
|-------|---------|------------|
| `PACKETNODE/<call>` | `{"status":"online"}` | On broker connect; refreshed every 30 minutes |
| `PACKETNODE/ax25/trace/bpqformat/<call>/sent/<port>` | JSON frame trace | Every L2 frame transmitted |
| `PACKETNODE/ax25/trace/bpqformat/<call>/rcvd/<port>` | JSON frame trace | Every L2 frame received |
| `PACKETNODE/kiss/<call>/sent/<port>` | Raw KISS-port TX bytes | KISS port transmit |
| `PACKETNODE/kiss/<call>/rcvd/<port>` | Raw frame bytes (AX.25 + a small BPQ header) | KISS port receive |
| `PACKETNODE/stats/session/<call>` | Session-stats text | `Events.c` session start / end / update |
| `PACKETNODE/event/<call>/pmsg` | BBS-message-event JSON | BPQMail message lifecycle (new / forwarded / read / killed) |

## Detail

### `PACKETNODE/<call>` — heartbeat

Sent on initial broker `CONNACK` and every 30 minutes thereafter.

```json
{"status":"online"}
```

Source: `mqtt.c::MQTTSendStatus`, called from `onConnect` and from
the `MQTTTimer` 30-minute branch.

### `PACKETNODE/ax25/trace/bpqformat/<call>/sent/<port>` and `.../rcvd/<port>`

Decoded BPQ-format trace of a single L2 frame.  Built by
`mqtt.c::jsonEncodeMessage`:

```json
{
  "from": "G7TEST",
  "to": "NODES",
  "payload": "<bpq-format trace string>",
  "port": 2,
  "timestamp": "14:22:49"
}
```

- `from` / `to` — call signs, padded
- `payload` — the human-readable monitor-style trace, the same
  format as the `Mon` log
- `port` — BPQ port number
- `timestamp` — local time, `HH:MM:SS`

Source: `mqtt.c::MQTTKISSTX` (transmit) and `MQTTKISSRX` (receive).
The TX path is invoked from `kiss.c:1000`.  The RX path is invoked
from `cMain.c:2437`.

### `PACKETNODE/kiss/<call>/sent/<port>` and `.../rcvd/<port>`

Raw bytes:

- **TX** — the KISS-encoded bytes the TNC was sent (FEND-framed,
  including any KISSOPTIONS=ACKMODE wrapping).  Source:
  `mqtt.c::MQTTKISSTX_RAW`, invoked from `kiss.c:1189` after the
  KISS encode path.
- **RX** — the raw frame bytes as received off the radio port,
  prefixed by a small BPQ-internal `MESSAGE` header.  The literal
  body bytes appear at the tail of the payload.  Source:
  `mqtt.c::MQTTKISSRX_RAW`, invoked from `kiss.c:1752`.

### `PACKETNODE/stats/session/<call>`

Plain-text session reports.  Sent from `Events.c:214` and `:400`.

### `PACKETNODE/event/<call>/pmsg`

BPQMail message lifecycle event:

```json
{
  "id": 42,
  "size": 256,
  "type": "P",
  "to": "TEST",
  "from": "N0CALL",
  "subj": "regression-test-subject",
  "event": "newmsg"
}
```

- `type` — `P` (personal) or `B` (bulletin)
- `event` — one of `newmsg` / `fwded` / `read` / `killed`,
  corresponding to `msg->status` values `N` / `F` / `R` / `K` in
  `mqtt.c::MQTTMessageEvent`.

Fired from `BPQMail.c:2858`, `MBLRoutines.c:206/312/371`,
`FBBRoutines.c:942`, `WebMail.c:2951/3951/4564`,
`WPRoutines.c:1508`.

## What is NOT published

For completeness — these are paths that touch MQTT functions but
do NOT result in published topics:

- **No subscriptions.**  LinBPQ never reads from MQTT; there are
  no commands to control the daemon over MQTT.
- **No global error / warning topic.**  Only the heartbeat exists
  for liveness — anything else relies on the trace topics being
  silent (or the heartbeat going stale).

## Testing

The integration suite (`tests/integration/test_mqtt.py`) stands up
a minimal in-process MQTT broker (`helpers/mqtt_broker.py`),
points linbpq at it via `MQTT_HOST`/`MQTT_PORT`, and asserts the
heartbeat plus a KISS-RX trace pair (decoded and raw) appear.
The broker is publish-only-aware (no QoS>0, no subscribe routing)
because that's all linbpq needs.
