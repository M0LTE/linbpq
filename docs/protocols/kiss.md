# KISS

KISS is the byte-stream framing format that connects a host to
a TNC.  It's older than the web and remarkably long-lived: every
USB or TCP-attached modem in 2026 still speaks some flavour of it.

The base spec ([Mike Chepponis / Phil Karn KA9Q, 1987][kiss-spec])
defines a tiny vocabulary — `FEND`/`FESC`/`TFEND`/`TFESC` for
framing, six command bytes (`DATA`, `TXDELAY`, `PERSIST`,
`SLOTTIME`, `TXTAIL`, `FULLDUP`) — that any AX.25 implementation
can drive.  Common extensions add multi-drop addressing,
checksumming, and ack-mode for deterministic TX completion
notification.

[kiss-spec]: https://github.com/packethacking/ax25spec/blob/main/doc/kiss.md

## Transports LinBPQ supports

| Transport | Driver | Notes |
|---|---|---|
| KISS over serial | `TYPE=ASYNC PROTOCOL=KISS` | Direct USB/serial TNCs (NinoTNC, TARPN-built etc.) |
| KISS over UDP | `TYPE=ASYNC PROTOCOL=KISS UDPPORT=...` | Datagram form for soft-modem peers (Direwolf has UDPport, FLDigi too) |
| KISS over TCP | `TYPE=ASYNC PROTOCOL=KISS TCPPORT=...` | Stream form, used by [kissproxy][kissproxy] and similar bridges to put a USB modem on TCP |
| KISS over I²C | `TYPE=I2C PROTOCOL=KISS I2CBUS=... I2CDEVICE=...` | TNC-PI on Raspberry Pi |
| KISS-style HF | `DRIVER=KISSHF` | Wrapper for HF-attached KISS modems, used with UZ7HO Sound Modem and similar |

[kissproxy]: https://github.com/m0lte/kissproxy

## Framing

```
FEND DATA <bytes> FEND
```

| Byte | Hex | Meaning |
|---|---|---|
| `FEND` | `0xC0` | Frame start / end. |
| `FESC` | `0xDB` | Escape. |
| `TFEND` | `0xDC` | After `FESC`, means literal `0xC0` in the payload. |
| `TFESC` | `0xDD` | After `FESC`, means literal `0xDB`. |

The first byte after the leading `FEND` is the *command byte*.
Lower nibble = command, upper nibble = port (so multi-port TNCs
like a TNC-PI 2-channel pi-hat can address each side):

| Cmd | Code | Meaning |
|---|---|---|
| `DATA` | `0` | The bytes following are an AX.25 frame to TX. |
| `TXDELAY` | `1` | Set TX-key delay in 10 ms units. |
| `PERSIST` | `2` | CSMA persistence (0–255). |
| `SLOTTIME` | `3` | CSMA slot time in 10 ms units. |
| `TXTAIL` | `4` | TX-key hold in 10 ms units. |
| `FULLDUP` | `5` | Full-duplex flag. |
| `SETHARDWARE` | `6` | Vendor-specific. |
| `RETURN` | `0xFF` | Exit KISS mode (some TNCs). |

LinBPQ writes `TXDELAY` / `TXTAIL` to the TNC in 10 ms units —
the cfg-keyword form is in milliseconds and divided by 10
before transmission.

## `KISSOPTIONS=` extensions

| Option | Effect |
|---|---|
| `POLLED` | Multi-drop polled mode — the host asks the TNC to TX rather than the TNC running CSMA itself. |
| `CHECKSUM` | Append a one-byte XOR checksum to every frame.  TNC drops frames where it doesn't match. |
| `ACKMODE` | Acknowledge-mode framing per the [Multi-Drop KISS spec][md-kiss] — frames carry a sequence number; the TNC sends back ACK_MODE responses on TX completion. |
| `SLAVE` | PC-multidrop with KISS TNCs — host listens for polls. |
| `D700` | Kenwood D700/D710 quirk: don't issue the KISS-exit sequence on shutdown (it accidentally turns off the TNC). |
| `PITNC` | TNC-PI on a Raspberry Pi over I²C. |
| `NOPARAMS` | Skip `TXDELAY` / `SLOTTIME` / etc. on init.  Use this when the TNC has its own front-panel parameter set you don't want overridden. |
| `FLDIGI` | KISS-over-UDP per FLDigi's framing — slight variant. |
| `TRACKER` | SCS Tracker init — sends the `RESET` byte sequence the Tracker needs. |

[md-kiss]: https://github.com/packethacking/ax25spec/blob/master/doc/multi-drop-kiss-operation.md

Multiple options combine with commas:

```
KISSOPTIONS=ACKMODE,CHECKSUM
```

## When the TNC owns the L2 timing

For most KISS modems LinBPQ does the L2 timing (FRACK / RETRIES
/ MAXFRAME), and the TNC just shovels frames in/out.  The
KISS `TXDELAY` / `PERSIST` / `SLOTTIME` / `TXTAIL` parameters
control the TNC's *channel access* — not the AX.25 retransmit
behaviour.

Some softmodems (Direwolf, SoundModem) handle their own channel
access and ignore the host's KISS parameters.  That's fine —
LinBPQ still issues the KISS commands at init, but tuning channel
access happens in the modem's own config in those cases.

## Multi-radio one-modem setups

A common HF / dual-band setup is a single Direwolf instance
exposing two KISS-TCP ports — one per soundcard channel.  In
LinBPQ each becomes its own `PORT` block:

```ini
PORT
 ID=Direwolf 144
 TYPE=ASYNC
 PROTOCOL=KISS
 IPADDR=127.0.0.1
 TCPPORT=8001
 ; ... usual L2 params ...
ENDPORT

PORT
 ID=Direwolf HF
 TYPE=ASYNC
 PROTOCOL=KISS
 IPADDR=127.0.0.1
 TCPPORT=8002
 ; ... usual L2 params, lower MAXFRAME, longer FRACK ...
ENDPORT
```

`INTERLOCK=<group>` on the PORT blocks if the two share a
single PTT and shouldn't TX simultaneously.
