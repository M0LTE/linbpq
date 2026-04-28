# Configuration reference

LinBPQ reads its configuration from `bpq32.cfg` in the working
directory at startup.  This page covers the **node** configuration
file format and every keyword the parser accepts.  BBS-specific
(`linmail.cfg`) and chat-specific (`chatconfig.cfg`) settings live
with their respective subsystem pages.

!!! note "Upstream and source"
    Re-presentation of John Wiseman's
    [BPQ32 Configuration File Description][upstream], adapted for
    LinBPQ.  Keyword list cross-checked against
    [`config.c`][config-src] (the global keywords table).

[upstream]: https://www.cantab.net/users/john.wiseman/Documents/BPQCFGFile.html
[config-src]: https://github.com/M0LTE/linbpq/blob/master/config.c

## File layout

```
; comment
KEYWORD=VALUE
ANOTHER=VALUE

PORT
 PORTKEYWORD=value
 CONFIG
 driver-specific lines
ENDPORT

ROUTES:
…
****

APPLICATION 1,…
```

A few rules the parser enforces:

- **Comments**: `;` at column 0 — and at column 1+ in PORT and CONFIG
  blocks — is a comment.  `/* … */` multi-line comments work but
  must start at column 1.
- **Hash comments**: `#` at top level lands in the unknown-keyword
  path and produces an `Ignored:` warning in the log; it doesn't
  fail the parse.  Inside `CONFIG ... ENDPORT` driver blocks `#`
  comments are silently accepted.
- **Case-insensitive keywords**: `simple=1`, `port`, `driver=Telnet`
  all work.
- **Trailing whitespace** on a value line is tolerated.
- **Multi-line text blocks** (`IDMSG:`, `BTEXT:`, `CTEXT:`,
  `INFOMSG:`, `IPGATEWAY ... ****`, `APRSDIGI ... ***`) end with
  `****` (four asterisks) on a line by themselves.  Note the
  trailing colon on the keyword.

## Quick start: SIMPLE mode

```ini
SIMPLE=1
NODECALL=N0CALL
NODEALIAS=TEST
LOCATOR=NONE

PORT
 ID=Telnet
 DRIVER=Telnet
 CONFIG
 TCPPORT=8010
 HTTPPORT=8080
 MAXSESSIONS=10
 USER=test,test,N0CALL,,SYSOP
ENDPORT
```

`SIMPLE=1` sets workable defaults for almost every global tunable —
buffers, timers, link counts, the lot.  The exact defaults applied,
from `config.c::simple()`:

| Keyword | Default | Keyword | Default |
|---|---|---|---|
| `BBS` | 1 | `BTINTERVAL` | 60 |
| `BUFFERS` | 999 | `C_IS_CHAT` | 1 |
| `FULL_CTEXT` | 1 | `HIDENODES` | 0 |
| `IDINTERVAL` | 10 | `IDLETIME` | 900 |
| `IPGATEWAY` | 0 | `L3TIMETOLIVE` | 25 |
| `L4DELAY` | 10 | `L4RETRIES` | 3 |
| `L4TIMEOUT` | 60 | `L4WINDOW` | 4 |
| `ENABLE_LINKED` | A | `MAXCIRCUITS` | 128 |
| `MAXNODES` | 250 | `MAXHOPS` | 4 |
| `MAXLINKS` | 64 | `MAXROUTES` | 64 |
| `MAXRTT` | 90 | `MINQUAL` | 150 |
| `NODE` | 1 | `NODESINTERVAL` | 30 |
| `OBSINIT` | 6 | `OBSMIN` | 5 |
| `PACLEN` | 236 | `T3` | 180 |
| `AUTOSAVE` | 1 | `SAVEMH` | 1 |

You only need to override one of these if you have a specific
reason; `SIMPLE=1` is the recommended starting point.

## Identification

| Keyword | Value | Effect |
|---|---|---|
| `NODECALL` | callsign | Required.  The node's primary callsign. |
| `NODEALIAS` | alias | Required.  Symbolic node name (up to 6 chars).  Appears in NODES tables across the network. |
| `NETROMCALL` | callsign | Optional.  Call used for NET/ROM L3 traffic.  Defaults to `NODECALL`. |
| `LOCATOR` | grid | Maidenhead grid reference (e.g. `IO91WJ`).  Used by the [node map][nodemap].  Use `NONE` to opt out. |
| `MAPCOMMENT` | text | Free-form text shown alongside this node on the map. |
| `EnableM0LTEMap` | `0`/`1` | Enable reporting to <https://m0lte.uk/map>. |
| `ENABLEOARCAPI` | `0`/`1` | Enable reporting to the OARC node-status API. |

[nodemap]: https://m0lte.uk/map

### Beacons and welcome text

```ini
IDMSG:
G8BPQ Test Node — IO91WJ
****

CTEXT:
Welcome to G8BPQ's test node.
Type ? for help.
****

INFOMSG:
Reading, UK.  Connected to the OARC mesh.
Sysop: tom@m0lte.uk
****

BTEXT:
=5828.54N/00612.69W- {BPQ32}
G8BPQ test node
****

IDINTERVAL=15      ; minutes between IDMSG transmissions
BTINTERVAL=15      ; minutes between BTEXT transmissions
```

| Block | When sent |
|---|---|
| `IDMSG:` | UI-frame ID, every `IDINTERVAL` minutes, on every port that has `BCALL=` or otherwise emits ID. |
| `CTEXT:` | Sent to a user when they connect to the node alias.  `FULL_CTEXT=1` sends to all connect targets, not just the alias. |
| `HFCTEXT=text` | Single-line CTEXT replacement on HF (Pactor / WINMOR / VARA / ARDOP) — saves bandwidth. |
| `INFOMSG:` | Returned in response to the `INFO` / `I` node command. |
| `BTEXT:` | UI-frame beacon, every `BTINTERVAL` minutes.  `BCALL=` per port sets the source call. |

## Capacity and security

| Keyword | Value | Effect |
|---|---|---|
| `BUFFERS` | int | Packet buffer pool.  `999` allocates as many as possible. |
| `MAXLINKS` | int | Concurrent L2 sessions (uplink + downlink + internode). |
| `MAXNODES` | int | Distinct L4 destinations the NODES table can hold. |
| `MAXROUTES` | int | Adjacent L3 neighbours. |
| `MAXCIRCUITS` | int | L4 circuits.  Each user session uses *two* — set ≥ `2 × users`. |
| `MAXHOPS` | int | INP3: largest hop count to admit to the routing table. |
| `MAXRTT` | int | INP3: largest round-trip time (centiseconds) to admit. |
| `PASSWORD` | string | Sysop password for the [`PASSWORD` challenge][pwcmd] command.  Replaces the legacy `PASSWORD.BPQ` file. |
| `BBS` | `0`/`1` | If `1`, applications may register and accept connects. |
| `NODE` | `0`/`1` | If `0`, users can only reach applications, not the bare node prompt. |

[pwcmd]: ../node-commands.md

## Compression and packet sizing

| Keyword | Default | Effect |
|---|---|---|
| `T3` | 180 | L2 link-validation timer (s).  Idle longer than this and the node sends `RR(P)` to check the peer. |
| `IDLETIME` | 900 | L2 idle disconnect timer (s). |
| `PACLEN` | 236 | Default packet length for node-originated frames.  Per-port `PACLEN` overrides for direct sessions; NET/ROM links can't carry > 236 without fragmentation. |
| `L2Compress` | 0 | If `1`, allow L2 link compression. |
| `L2CompMaxframe` | 3 | Max frames of compressed L2 data outstanding. |
| `L4Compress` | 0 | If `1`, allow L4 compression. |
| `L4CompMaxframe` | 3 | Max frames of compressed L4 data. |
| `L4CompPaclen` | 236 | Packet size for compressed L4 frames. |

## NET/ROM

| Keyword | Default | Effect |
|---|---|---|
| `NODESINTERVAL` | 30 | Minutes between NODES broadcasts. |
| `OBSINIT` | 6 | Initial obsolescence count for new NODES entries. |
| `OBSMIN` | 5 | Minimum obsolescence count to include in outgoing NODES broadcasts. |
| `L3TIMETOLIVE` | 25 | Maximum L3 hops. |
| `L4RETRIES` | 3 | L4 retry limit. |
| `L4TIMEOUT` | 60 | L4 retry interval (s). |
| `L4DELAY` | 10 | L4 delayed-ACK timer (s). |
| `L4WINDOW` | 4 | L4 send window. |
| `MINQUAL` | 150 | Minimum quality for a destination to enter the NODES table. |
| `HIDENODES` | 0 | If `1`, suppress display of nodes whose alias starts with `#`. |
| `OnlyVer2point0` | 0 | If `1`, force AX.25 v2.0 on all node-to-node links (default is v2.2). |
| `PREFERINP3ROUTES` | 0 | If `1`, INP3 routes win over NODES routes (default uses INP3 only as fallback). |
| `RIFInterval` | 0 | Minutes between Routing Information Frame emissions (`SENDRIF`). |

## Persistence

| Keyword | Effect |
|---|---|
| `AUTOSAVE` | If `1`, write `BPQNODES.dat` (NODES + ROUTES) on shutdown.  `SAVENODES` does the same on demand. |
| `SAVEMH` | If `1`, persist the MH list across restarts. |
| `SAVEAPRSMSGS` | If `1`, persist the APRS message store across restarts. |

## Application registration

```ini
APPLICATION 1,BBS,,N0CALL-1,BPQBBS,200
APPLICATION 2,CHAT,,N0CALL-2,BPQCHT,255
APPLICATION 3,DX,C DXCLUS
```

Modern form (recommended):

```
APPLICATION n, CMD, [NewCommand], [Call], [Alias], [Quality], [L2Alias]
```

| Field | Meaning |
|---|---|
| `n` | Application slot 1–32. |
| `CMD` | What the user types at the node prompt. |
| `NewCommand` | Optional.  If set, `CMD` runs this command line (e.g. `C DXCLUS`).  Empty for in-process apps (BBS / chat). |
| `Call` | Optional.  Callsign at which other nodes can connect to invoke this application. |
| `Alias` | Optional.  NODES alias for `Call`.  Add this and `Quality` to advertise the application to the network. |
| `Quality` | Optional.  Quality for the NODES advertisement. |
| `L2Alias` | Optional.  Additional L2-direct alias for the application call. |

The legacy form (`APPLICATIONS=BBS,CHAT,DX/C DXCLUS` plus
`APPL1CALL=` / `APPL1ALIAS=` / `APPL1QUAL=`) still works for the
first eight applications.

## PORT blocks

A `PORT` block declares a hardware or virtual interface.  The
shape:

```ini
PORT
 ID=Description
 DRIVER=DriverName        ; or TYPE=ASYNC for built-in KISS-on-serial
 QUALITY=200              ; default L4 quality for nodes heard here
 ; ... other PORT keywords ...
 CONFIG
 driver-specific lines
ENDPORT
```

The `CONFIG` keyword starts a sub-block whose contents are
interpreted by the driver, not the main config parser — the keyword
syntax inside is whatever the driver wants (see e.g. the
[AX/IP over UDP page][axip] for the BPQAXIP CONFIG keywords).

[axip]: ../protocols/axip.md

### PORT-level keywords

| Keyword | Effect |
|---|---|
| `PORTNUM=n` | Port number (default sequential). |
| `ID=text` | Description (≤ 30 chars), shown in `PORTS`. |
| `TYPE=…` | Hardware class — `ASYNC`, `I2C`, `INTERNAL`, `EXTERNAL`.  Use `DRIVER=` for built-in drivers. |
| `DRIVER=name` | Built-in driver: `Telnet`, `BPQAXIP`, `BPQtoAGW`, `KISSHF`, `UZ7HO`, `VARA`, `ARDOP`, `FLDigi`, `KAMPactor`, `AEAPactor`, `SCSPactor`, `SCSTracker`, `TrackeMulti`, `HALDriver`, `MULTIPSK`, `WinRPR`, `HSMODEM`. |
| `DLLNAME=file.dll` | Windows-only.  Use a third-party `.dll` driver. |
| `PROTOCOL=…` | `HDLC` / `KISS` / `NETROM` / `PACTOR` / `WINMOR` / `ARQ`. |
| `QUALITY=n` | Default L4 quality for nodes heard on this port.  `0` suppresses NODES emission and L3/L4 activity entirely. |
| `MINQUAL=n` | Min quality to include a destination in NODES broadcasts on this port. |
| `QUALADJUST=n` | Reduce broadcast quality of a destination by this percentage if its best route is on this same port. |
| `MAXFRAME=n` | L2 outstanding-frames limit. |
| `RETRIES=n` | L2 retry limit. |
| `FRACK=ms` | L2 timeout (ms). |
| `RESPTIME=ms` | L2 delayed-ACK timer (ms). |
| `PACLEN=n` | Per-port packet length override. |
| `NODESPACLEN=n` | Max length of a NODES broadcast frame. |
| `IDLETIME=s` | L2 idle disconnect override. |
| `BBSFLAG=NOBBS` | Forbid direct BBS connects on this port. |
| `PORTCALL=call` | Extra L2 call this port answers to. |
| `PORTALIAS=alias`, `PORTALIAS2=alias` | Extra L2 aliases. |
| `BCALL=call` | Source call for beacon and ID frames on this port. |
| `ALIAS_IS_BBS=0/1` | If `1`, `PORTCALL`/`PORTALIAS` connect to the BBS, not the node. |
| `VALIDCALLS=…` | Comma-separated allowlist (≤ 40 calls per line, ≤ 256 bytes total per line; multiple `VALIDCALLS=` lines allowed). |
| `PERMITTEDAPPLS=…` | Restrict which APPLICATION numbers are reachable on this port. |
| `USERS=n` | Limit concurrent L2 sessions on this port (0 = no limit; checked on incoming connect only). |
| `INTERLOCK=n` | Group ports to prevent simultaneous TX (e.g. Pactor + WINMOR sharing one radio). `0` = no locking. |
| `TXPORT=n` | Use this port's TX path on a different port (single-TX, multi-RX setups). |
| `MHEARD=Y/N` | Default `Y`.  `N` disables MH list updates from this port. |
| `WL2KREPORT=…` | Report channel info to the Winlink database — for HF gateway operators. |
| `L3ONLY=0/1` | If `1`, refuse user-initiated downlinks on this port (HOST sessions still allowed). |
| `INP3ONLY=0/1` | If `1`, accept INP3 routing only — ignore NODES broadcasts. |
| `IGNOREUNLOCKEDROUTES=0/1` | If `1`, only LOCKED ROUTES entries can broadcast NODES on this port. |
| `NOKEEPALIVES=0/1` | If `1`, mark routes heard here as "no keepalive". |
| `HIDE=0/1` | If `1`, omit from `PORTS` display and AGW port list. |
| `UIONLY=0/1` | If `1`, no L2 connects accepted — UNPROTO traffic only (APRS digi etc). |
| `UNPROTO=…` | Default UNPROTO destination + via path (comma-separated, no `VIA` keyword). |
| `M0LTEMapInfo=text` | Per-port info string for the node-map publication. |
| `PortFreq=hz` | Operating frequency, used by the node-map and Winlink reporting. |

### Digipeater keywords

| Keyword | Effect |
|---|---|
| `DIGIFLAG=0/1/255` | `0` = no digi.  `1` = digi everything.  `255` = UI frames only. |
| `DIGIPORT=n` | Cross-port: send digi'd frames out on this port (`0` = same as RX). |
| `DIGIMASK=hex` | Bitmask of ports for digi cross-fanout (paired with `DIGIFLAG=255`). |
| `XDIGI=call,n[,UI]` | Frames addressed to `call` go to port `n`; add `UI` to restrict to UI frames. |
| `MAXDIGIS=n` | Limit count of digipeaters in the path of an incoming connect on this port. |

### Modem-specific keywords

| Keyword | Effect |
|---|---|
| `IOADDR=hex` | I/O base address for HDLC cards. |
| `INTLEVEL=n` | IRQ for HDLC cards. |
| `SPEED=n` | Radio bitrate for HDLC; serial bitrate for KISS / NET-ROM. |
| `CHANNEL=A/B/…` | Channel selector for dual-port KISS or HDLC. |
| `COMPORT=…` | Serial port name (`/dev/ttyUSB0` on Linux). |
| `IPADDR=…` / `UDPPORT=n` / `UDPRXPORT=n` / `UDPTXPORT=n` / `TCPPORT=n` | KISS-over-UDP / TCP. |
| `I2CBUS=n` / `I2CDEVICE=n` | KISS over I²C (TNC-PI). |
| `RIGPORT=n` | Couple to a RIGCONTROL block for PTT and frequency control. |
| `KISSOPTIONS=…` | Comma-separated list of KISS extensions: `POLLED`, `CHECKSUM`, `ACKMODE`, `SLAVE`, `D700`, `PITNC`, `NOPARAMS`, `FLDIGI`, `TRACKER`. |
| `KISSCOMMAND=…` | Send a literal KISS command on init. |
| `TXDELAY=ms` / `TXTAIL=ms` / `SLOTTIME=ms` / `PERSIST=n` | Standard KISS timing parameters (TXDELAY/TXTAIL in ms; the binary scales /10 to write 10 ms units to the TNC). |
| `FULLDUP=0/1` | KISS full-duplex flag, or HDLC TX-during-DCD. |
| `SOFTDCD=0/1` | HDLC soft DCD (frame-detection rather than carrier-detect). |
| `CWID=call` | CWID identification (HDLC cards, every 29 minutes). |
| `CWIDTYPE=ONOFF` | Use OOK rather than tone keying. |
| `SMARTID=0/1` | Smart-ID — only ID when transmissions actually occurred. |
| `QTSMPort=n` | QTSM coupling for paired QTSM driver instances. |

## Locked routes

```
ROUTES:
GM8BPQ-5,192,2,,5,,1
G8BPQ-9,180,3
****
```

Old comma-separated form:

```
CALL, QUAL, PORT [, MAXFRAME] [, FRACK] [, PACLEN] [, INP3]
```

Optional fields can be omitted with empty positions.  `INP3`:
`0`/null = off, `1` = on, `2` = on with no L2 keepalives.

New keyword-value form:

```
CALL=GM8BPQ-5, PORT=2, QUALITY=192, FRACK=5, PACLEN=236, INP3=1, TCP=0.0.0.0:53119
CALL=G8BPQ-9, PORT=2, noV2.2=1
```

The `TCP=` field carries the NET/ROM-over-TCP listen address.

!!! warning "Parser bug — keyword form misparses on some configs"
    [Issue #12][issue12] tracks a separator-set inconsistency at
    `config.c:1619` that misparses the keyword=value form in some
    cases.  The comma form is the safer choice today.

[issue12]: https://github.com/M0LTE/linbpq/issues/12

## TNC emulators

`TNCPORT` blocks expose external TNC2 / DED / Kantronics / SCS
host-mode interfaces — applications speak host-mode to LinBPQ as
if it were a TNC:

```ini
TNCPORT
 COMPORT=/dev/ttyS5
 TYPE=DED
 APPLFLAGS=6
 APPLNUM=1
 CHANNELS=4
ENDPORT
```

| Keyword | Effect |
|---|---|
| `COMPORT=…` | Serial device.  On Linux a PTY is created. |
| `TYPE=…` | Emulation: `TNC2` / `DED` / `KANT` / `SCS`. |
| `APPLNUM=n` | Application slot to attach to (or use `APPLMASK=hex`). |
| `APPLFLAGS=n` | Sum of: `1` (pass cmds to app), `2` (CONNECTED to user), `4` (CONNECTED to app), `8` (`^D` = disconnect). |
| `CHANNELS=n` | Channel count; TNC2 only supports 1. |
| `POLLDELAY=ms` | Throttle BPQ-VCOM polling to reduce CPU. |

## AGW emulator

```ini
AGWPORT=8000
AGWSESSIONS=5
AGWMASK=1
```

Lets AGW-protocol clients (Direwolf-companion apps, SoundModem GUI
consumers, third-party loggers) talk to LinBPQ.  `AGWMASK` is a
bitmask of application slots the AGW socket can reach.

## Bridging

```
BRIDGE 1=4,5
BRIDGE 4=1
```

Forwards every L2 frame received on the source port to the
listed destination ports verbatim.  Unlike digipeating the path
isn't examined or rewritten — useful for socat-based virtual
serial ports linking out to APRS clients like Xastir.

## Subsystem toggles

| Keyword | Value | Effect |
|---|---|---|
| `IPGATEWAY` | block | Open the IP-over-AX.25 gateway config block (terminated by `****`).  See [IP gateway][ipgw].  The `IPGATEWAY=0`/`IPGATEWAY=1` form is no longer accepted by the parser. |
| `APRSDIGI` | block | Open an APRS digi/iGate config block — see [APRS][aprs]. |
| `LINMAIL` | flag | Same as the `mail` command-line argument: start the BBS. |
| `LINCHAT` | flag | Same as the `chat` command-line argument: start the chat server. |
| `MQTT` | `0`/`1` | Publish runtime events to MQTT (paired with `MQTT_HOST`/`MQTT_PORT`/`MQTT_USER`/`MQTT_PASS`). |
| `ENABLEEVENTS` | `0`/`1` | Enable the events / OARC API output. |
| `ENABLEADIFLOG` | `0`/`1` | Write ADIF log entries for completed connections. |
| `LogL4Connects` / `LogAllConnects` | `0`/`1` | Per-class connect logging. |
| `MONTOFILE` | `0`/`1` | Mirror the monitor stream to a file (`MonTrace.txt`). |

[aprs]: ../subsystems/aprs.md
[ipgw]: ../subsystems/ipgateway.md

## Driver-specific blocks

Drivers consume their own keywords inside `CONFIG ... ENDPORT`.
The shape varies wildly per driver; each gets its own page on
this site as the rewrite progresses:

- [AX/IP over UDP](../protocols/axip.md) — `BPQAXIP`
- KISS over TCP / UDP — `KISSHF`, `UZ7HO`
- AGW emulator (outbound) — `BPQtoAGW`
- Pactor families — `KAMPactor`, `SCSPactor`, `SCSTracker`,
  `TrackeMulti`, `AEAPactor`, `HALDriver`
- VARA / ARDOP — `VARA`, `ARDOP`
- FLDigi / FLARQ — `FLDigi`
- WinRPR — `WinRPR`
- HSMODEM — `HSMODEM`

See the [Protocols and interfaces][protos] section for what's
been written up so far.

[protos]: ../protocols/index.md

## Obsolete and ignored keywords

These keywords parse but do nothing (kept for backwards
compatibility with older cfg files):

`EMS`, `DEDHOST` (XXDEDHOST in source), `DESQVIEW`,
`HOSTINTERRUPT`, `TRANSDELAY`, `L4APPL`, `BBSCALL`,
`BBSALIAS`, `BBSQUAL`.

The standalone `UNPROTO=` at top level is also a no-op (only the
per-port `UNPROTO=` does anything today).

