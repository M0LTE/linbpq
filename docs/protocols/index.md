# Protocols and interfaces

LinBPQ implements a stack of amateur-radio protocols on the
inside and exposes them through a handful of network-side
interfaces on the outside.  This section documents both.

## Layered overview

```
┌──────────────────────── applications ────────────────────────┐
│   BBS         Chat         APRS digi/iGate     IP gateway    │
└─────┬─────────┬───────────────┬───────────────────┬──────────┘
      │ L4 (NET/ROM connection-oriented circuits)              
┌─────┴─────────┴───────────────┴───────────────────┴──────────┐
│                       NET/ROM L3                             │
│           (NODES propagation, INP3 routing)                  │
├──────────────────────────────────────────────────────────────┤
│                       AX.25 L2                               │
│      (frame format, retransmits, flow control)               │
├──────────────────────────────────────────────────────────────┤
│  KISS-on-serial │ KISS-on-TCP │ AX/IP-UDP │ AGW │ NET/ROM-TCP│
│  HDLC card      │ Pactor      │ ARDOP/VARA│ FLDigi  │ HSMODEM│
└──────────────────────────────────────────────────────────────┘
```

A `PORT` block in `bpq32.cfg` declares one row of the bottom
band — a transport — and binds it to a `DRIVER=` (built-in or
`.dll`) plus driver-specific keywords inside `CONFIG ... ENDPORT`.

## Pages in this section

| Topic | Page |
|---|---|
| AX.25 link layer | [AX.25](ax25.md) |
| NET/ROM L3 / L4 | [NET/ROM](netrom.md) |
| KISS framing (serial / TCP / UDP) | [KISS](kiss.md) |
| AX.25 over IP (UDP / TCP / proto-93) | [AX/IP over UDP](axip.md) |
| AGW emulator (BPQtoAGW driver) | [BPQtoAGW](bpqtoagw.md) |
| Applications Interface (CMDPORT, AGW outbound) | [Applications Interface](apps-interface.md) |
| FBB compressed inter-BBS forwarding | [FBB forwarding](fbb-forwarding.md) |

## External interfaces (network-side)

These are the network listeners LinBPQ opens for client tooling
to talk to it:

| Interface | Default port | Source |
|---|---|---|
| Telnet (node prompt + login challenge) | TCPPORT | `TelnetV6.c` |
| Web admin / BBS web UI / JSON API | HTTPPORT | `HTTPcode.c` |
| FBB mode (raw TCP for forwarding) | FBBPORT | `TelnetV6.c` |
| AGW emulator (inbound) | AGWPORT | `AGWAPI.c` |
| LinBPQ Apps Interface | CMDPORT | `cMain.c` |
| Aux JSON API | APIPORT | `nodeapi.c` |
| SNMP (when IPGATEWAY enabled) | SNMPPORT (default 161) | `IPCode.c` |
| MQTT (outbound) | MQTT_HOST:MQTT_PORT | `mqtt.c` |
| Winlink CMS (outbound) | CMS server | `CMSAuth.c` |

## External interfaces (radio side)

| Driver | Transport |
|---|---|
| `KISSHF` | KISS over serial / TCP |
| `BPQAXIP` | AX.25 framed over UDP, TCP, or IP-protocol-93 |
| `BPQtoAGW` | AGW protocol (TCP) — to SoundModem, Direwolf, AGWPE |
| `UZ7HO` | UZ7HO Sound Modem in session mode |
| `VARA` | VARA HF / VARA FM (TCP control + data sockets) |
| `ARDOP` | ARDOP TNC (same wire shape as VARA) |
| `FLDigi` | FLDigi / FLARQ (ARQ + XML-RPC sockets) |
| `KAMPactor` | Kantronics KAM in Pactor mode (serial) |
| `AEAPactor` | AEA / Timewave PK-232 family (serial) |
| `SCSPactor` | SCS PTC family (serial) |
| `SCSTracker`, `TrackeMulti` | SCS Tracker / DSP-4100 (serial) |
| `HALDriver` | HAL DXP-38 / Clover-II (serial) |
| `MULTIPSK` | MULTIPSK (TCP) |
| `WinRPR` | SCS-Tracker reply protocol (TCP) |
| `HSMODEM` | UDP-attached HSMODEM |

Each driver has (or will have) its own page.  The most-used ones
are linked above.
