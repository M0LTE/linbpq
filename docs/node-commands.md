# LinBPQ Node Commands

> **AI-generated content.** This document was produced by an AI assistant
> (Claude) by reading the LinBPQ source. It has not been reviewed by the
> upstream author. It may contain errors, omissions or out-of-date
> information; treat it as a starting point and verify against the source
> (links throughout point to the relevant file and line) before relying
> on any detail.

This is a reference for every command that can be entered at the LinBPQ /
BPQ32 node prompt. It is generated from the dispatch table `COMMANDS[]` in
[`Cmd.c`](../Cmd.c) and the individual command handlers in `Cmd.c`,
`IPCode.c`, `TelnetV6.c`, `RHP.c`, `APRSCode.c`, `AGWAPI.c` and
`CommonCode.c`.

## Conventions

- Commands are not case-sensitive; the parser uppercases the input line
  before matching (the original case is preserved for sub-arguments where
  it matters, e.g. `RADIO`, `UZ7HO`).
- Most commands can be abbreviated. The **Abbr** column in each table
  shows the shortest accepted prefix — so an `Abbr` of `3` means you
  must type at least the first three characters. Anything you type
  beyond the prefix must still be a leading substring of the full
  command name. For example, `LISTEN` has `Abbr = 3`, so `LIS`,
  `LIST`, `LISTE` and `LISTEN` all work, but `LZ` does not. Note that
  `LINKS` (Abbr = 1) is matched first when the parser walks the
  dispatch table, so `L`, `LI` and `LIN` resolve to `LINKS` — only
  `LIS` and longer reach `LISTEN`.
- Commands marked **SYSOP** require a successful `PASSWORD` exchange or a
  session that the node treats as already authenticated (BPQ host,
  Telnet sysop login, etc.).
- Where a port number is required and the node is configured with a
  single port, the port number may be omitted (e.g. `LISTEN`, `UNPROTO`,
  `MH`).
- A trailing `\r` (carriage return) terminates a command. Multiple
  commands may be separated with `;` in the same packet.

---

## Quick reference

### Session and connection

| Command | Abbr | Sysop | Summary |
|---------|-----:|:-----:|---------|
| [`CONNECT` / `C`](#connect) | 1 | | Connect to a node, station or service. |
| [`NC`](#nc) | 2 | | Same as `CONNECT` (alternative entry). |
| [`ATTACH`](#attach) | 1 | | Attach to a Pactor / VARA / Telnet stream. |
| [`BYE`](#bye) | 1 | | Disconnect the current session. |
| [`QUIT`](#bye) | 1 | | Alias for `BYE`. |
| [`PASSWORD`](#password) | 8 | | Authenticate as sysop. |

### Help and information

| Command | Abbr | Sysop | Summary |
|---------|-----:|:-----:|---------|
| [`?`](#question) | 1 | | List the commands available on this node. |
| [`HELP`](#help) | 1 | | Print the contents of `NodeHelp.txt`. |
| [`INFO`](#info) | 1 | | Print the configured `INFOMSG`. |
| [`VERSION`](#version) | 1 | | Print BPQ32/LinBPQ version. |

### Browsing the network

| Command | Abbr | Sysop | Summary |
|---------|-----:|:-----:|---------|
| [`NODES`](#nodes) | 1 | | List, search or inspect known NET/ROM nodes. |
| [`ROUTES`](#routes) | 1 | | List neighbours / set route quality. |
| [`LINKS`](#links) | 1 | | List active L2 links / reset a link. |
| [`USERS`](#users) | 1 | | List active L4 circuits. |
| [`PORTS`](#ports) | 1 | | List node ports (add `E` for extended status). |
| [`STREAMS`](#streams) | 6 | | List BPQ host streams. |
| [`STATS`](#stats) | 1 | | System and per-port counters. |
| [`MHEARD` / `MH`](#mheard) | 1 | | Heard list for a port (variants `MHL`, `MHU`, `MHV`, `MHLV`, `MHUV`). |
| [`NRR`](#nrr) | 1 | | Send a NET/ROM Record-Route trace to a node. |

### Per-session settings

| Command | Abbr | Sysop | Summary |
|---------|-----:|:-----:|---------|
| [`PACLEN`](#paclen) | 3 | | Get / set the L4 packet length on this session. |
| [`IDLETIME`](#idletime) | 4 | | Get / set this session's idle timeout (seconds). |
| [`L4T1`](#l4t1) | 2 | | Get / set this session's L4 timeout. |

### Listening and unconnected traffic

| Command | Abbr | Sysop | Summary |
|---------|-----:|:-----:|---------|
| [`LISTEN` / `LIS`](#listen) | 3 | | Monitor unproto traffic on one or more ports. |
| [`CQ`](#cq) | 2 | | Send a CQ beacon on the listened port. |
| [`UNPROTO`](#unproto) | 2 | | Enter UI / unproto transmit mode. |

### Networking diagnostics

| Command | Abbr | Sysop | Summary |
|---------|-----:|:-----:|---------|
| [`PING`](#ping) | 2 | | Send an ICMP echo via the BPQ IP gateway. |
| [`ARP`](#arp) | 3 | | Display / clear the IP-gateway ARP table. |
| [`NAT`](#nat) | 3 | | Display the IP-gateway NAT table. |
| [`IPROUTE`](#iproute) | 3 | | Display the IP routing table (filterable). |
| [`AXRESOLVER`](#axresolver) | 3 | | Display the AXIP resolver table for a port. |
| [`AXMHEARD`](#axmheard) | 3 | | Display the AXIP heard table for a port. |
| [`AGWSTATUS`](#agwstatus) | 3 | | Show AGWPE-emulation sockets / sessions. |
| [`TELSTATUS`](#telstatus) | 3 | | Show Telnet server sockets / users. |
| [`RHP`](#rhp) | 3 | | Show Remote Host Protocol sessions. |
| [`QTSM`](#qtsm) | 4 | | Show QtSoundModem modem / centre frequency. |

### APRS and Winlink

| Command | Abbr | Sysop | Summary |
|---------|-----:|:-----:|---------|
| [`APRS`](#aprs) | 2 | partial | APRS heard list and IGate sub-commands. |
| [`WL2KSYSOP`](#wl2ksysop) | 5 | yes | Display / update the Winlink sysop record. |

### Radio control

| Command | Abbr | Sysop | Summary |
|---------|-----:|:-----:|---------|
| [`RADIO`](#radio) | 3 | | Issue a `RIGCONTROL` command. |
| [`UZ7HO`](#uz7ho) | 5 | | Send `FREQ` / `MODEM` / `FLAGS` to a UZ7HO modem. |

### Sysop — port parameters (`PORTPARM PORT [VALUE]`)

These commands all take the form `CMD PORT` to display, or
`CMD PORT VALUE` to set a port-control byte. They require sysop status.

| Command | Abbr | Field |
|---------|-----:|-------|
| [`TXDELAY`](#port-parameters)    | 3 | `PORTTXDELAY` |
| [`MAXFRAME`](#port-parameters)   | 3 | `PORTWINDOW` |
| [`RETRIES`](#port-parameters)    | 3 | `PORTN2` |
| [`FRACK`](#port-parameters)      | 3 | `PORTT1` |
| [`RESPTIME`](#port-parameters)   | 3 | `PORTT2` |
| [`PPACLEN`](#port-parameters)    | 3 | `PORTPACLEN` (port default packet length) |
| [`QUALITY`](#port-parameters)    | 3 | `PORTQUALITY` |
| [`PERSIST`](#port-parameters)    | 2 | `PORTPERSISTANCE` |
| [`TXTAIL`](#port-parameters)     | 3 | `PORTTAILTIME` |
| [`XMITOFF`](#port-parameters)    | 7 | `PORTDISABLED` |
| [`DIGIFLAG`](#port-parameters)   | 5 | `DIGIFLAG` |
| [`DIGIPORT`](#port-parameters)   | 5 | `DIGIPORT` |
| [`MAXUSERS`](#port-parameters)   | 4 | `USERS` |
| [`L3ONLY`](#port-parameters)     | 6 | `PORTL3FLAG` |
| [`BBSALIAS`](#port-parameters)   | 4 | `PORTBBSFLAG` |
| [`INP3ONLY`](#port-parameters)   | 8 | `INP3ONLY` |
| [`ALLOWINP3`](#port-parameters)  | 9 | `ALLOWINP3` |
| [`ENABLEINP3`](#port-parameters) | 10 | `ENABLEINP3` |
| [`FULLDUP`](#port-parameters)    | 4 | `FULLDUPLEX` |
| [`SOFTDCD`](#port-parameters)    | 4 | `SOFTDCDFLAG` |
| [`EXTRESTART`](#extrestart)      | 10 | Restart an external (TNC) port. |

### Sysop — switch globals

These set node-wide variables. Form is `CMD` (display) or `CMD VALUE`
(set). 8-bit values use `SWITCHVAL`; 16-bit values use `SWITCHVALW`.

| Command | Abbr | Variable | Width |
|---------|-----:|----------|------:|
| [`OBSINIT`](#switch-globals)      | 7 | `OBSINIT` | 8 |
| [`OBSMIN`](#switch-globals)       | 6 | `OBSMIN` | 8 |
| [`NODESINT`](#switch-globals)     | 8 | `L3INTERVAL` | 8 |
| [`L3TTL`](#switch-globals)        | 5 | `L3LIVES` | 8 |
| [`L4RETRIES`](#switch-globals)    | 5 | `L4N2` | 8 |
| [`L4TIMEOUT`](#switch-globals)    | 5 | `L4T1` | 16 |
| [`T3`](#switch-globals)           | 2 | `T3` | 16 |
| [`NODEIDLETIME`](#switch-globals) | 8 | `L4LIMIT` | 16 |
| [`LINKEDFLAG`](#switch-globals)   | 10 | `LINKEDFLAG` | 8 |
| [`IDINTERVAL`](#switch-globals)   | 5 | `IDINTERVAL` | 8 |
| [`MINQUAL`](#switch-globals)      | 7 | `MINQUAL` | 8 |
| [`FULLCTEXT`](#switch-globals)    | 6 | `FULL_CTEXT` | 8 |
| [`HIDENODES`](#switch-globals)    | 8 | `HIDENODES` | 8 |
| [`L4DELAY`](#switch-globals)      | 7 | `L4DELAY` | 8 |
| [`L4WINDOW`](#switch-globals)     | 6 | `L4DEFAULTWINDOW` | 8 |
| [`BTINTERVAL`](#switch-globals)   | 5 | `BTINTERVAL` | 8 |
| [`DEBUGINP3`](#switch-globals)    | 8 | `DEBUGINP3` | 8 |
| [`RIFINTERVAL`](#switch-globals)  | 11 | `RIFInterval` | 16 |
| [`MAXHOPS`](#switch-globals)      | 7 | `MaxHops` | 8 |
| [`PREFERINP3`](#switch-globals)   | 10 | `PREFERINP3ROUTES` | 8 |
| [`MAXRTT`](#switch-globals)       | 6 | `MAXRTT` | 16 |
| [`MAXTT`](#switch-globals)        | 6 | `MAXRTT` (alias of `MAXRTT`) | 16 |
| [`MONTOFILE`](#switch-globals)    | 9 | `MONTOFILEFLAG` | 8 |

### Sysop — actions and reconfiguration

| Command | Abbr | Summary |
|---------|-----:|---------|
| [`SAVENODES`](#savenodes)         | 8  | Persist NET/ROM nodes and routes tables to disk. |
| [`SAVEMH`](#savemh)               | 6  | Persist MHeard tables to disk. |
| [`POLLNODES`](#pollnodes)         | 8  | Send an INP3 nodes-poll on a port. |
| [`SENDNODES`](#sendnodes)         | 8  | Send NET/ROM `NODES` broadcast (`0` = all). |
| [`SENDRIF`](#sendrif)             | 7  | Send INP3 RIF to a single neighbour. |
| [`REBOOT`](#reboot)               | 6  | Reboot the host machine. |
| [`RESTART`](#restart)             | 7  | Restart LinBPQ / BPQ32. |
| [`RESTARTTNC`](#restarttnc)       | 10 | Restart the helper program for a TNC port. |
| [`RIGRECONFIG`](#rigreconfig)     | 8  | Re-read configuration into RIGCONTROL. |
| [`TELRECONFIG`](#telreconfig)     | 4  | Re-read Telnet config (`PORT [USERS|ALL]`). |
| [`STOPPORT`](#stopport)           | 4  | Close a (KISS / external) port. |
| [`STARTPORT`](#startport)         | 5  | Open a (KISS / external) port. |
| [`STOPCMS`](#stopcms)             | 7  | Disable Winlink CMS forwarding on a Telnet port. |
| [`STARTCMS`](#startcms)           | 8  | Enable Winlink CMS forwarding on a Telnet port. |
| [`STOPROUTE`](#stoproute)         | 9  | Disable a NET/ROM neighbour route. |
| [`STARTROUTE`](#startroute)       | 10 | Re-enable a stopped neighbour route. |
| [`KISS`](#kiss)                   | 4  | Send raw KISS bytes to a TNC. |
| [`FINDBUFFS`](#findbuffs)         | 4  | Dump lost-buffer info to the debug log. |
| [`GETPORTCTEXT`](#getportctext)   | 9  | Re-read all `PortNCTEXT.txt` files. |
| [`VALIDCALLS`](#validcalls)       | 5  | Show / set permitted callsigns on a port. |
| [`EXCLUDE`](#exclude)             | 4  | Show / add / clear the connect-exclude list (Windows build). |
| [`DUMP`](#dump)                   | 4  | Write a minidump file (Windows build). |

### Application aliases

The 32 entries originally shown as `*** ******` in the dispatch table are
filled with whatever **APPLICATION**s the sysop has configured (`BBS`,
`CHAT`, `MAIL`, etc.) — see [`APPL`](#application-commands). Each acts
as a direct command to attach to that application's host stream, with
optional `PASSWORD` and an `ALIAS` that is re-injected as a node command.

Unconfigured slots stay as `************` and never match any input.

### Host-protocol pseudo-commands

These dispatch-table entries are not for human use — they are token
strings that gateway / host programs send so that the node will react
in a defined way.

| Command | Abbr | Summary |
|---------|-----:|---------|
| [`*** LINKED`](#linked) | 10 | A gateway / BBS host declares the real callsign of the user behind its session. |
| [`..FLMSG`](#flmsg)     | 7  | An incoming Telnet connection identifies itself as FLMSG; the node disconnects. |

---

## Detailed reference

<a id="connect"></a>
### `CONNECT` / `C` *(abbr: 1)*

Source: `CMDC00` in `Cmd.c:2558`.

```
C [!]<call>[-ssid] [VIA <digi>[,<digi>...]]
C <port> <call>[-ssid] [VIA <digi>...]
C <service>@<node>[ S]
```

Without arguments the node responds `Invalid Call`. The connect logic
runs in this order:

1. **Service connect.** If the argument contains `@` it is treated as
   `service@node` (NET/ROM-X). Numeric services are accepted.
2. **APPL match.** If the call matches a configured application's alias
   or callsign, the corresponding application command is run (any alias
   text is re-injected as a node command).
3. **NET/ROM destination.** If the call (or 6-character alias on an `-0`
   SSID) matches a known NET/ROM destination, an L4 connect is sent.
   Prefix the call with `!` to skip this lookup and force a downlink.
4. **L2 downlink.** Otherwise an L2 connect on the specified port (or
   the only port if the node has one) is started. Multi-port systems
   require an explicit port: `C 1 G8BPQ-7`.
5. **Pactor / VARA / WINMOR / ARDOP via.** A connect of the form
   `C <port> <call> VIA WINMOR` (etc.) is converted into an
   [`ATTACH`](#attach) followed by a connect command sent to the TNC.

Trailing flags: `S` requests a *stay* connect (keep the host stream
allocated after disconnect), `Z` requests a spy/listen-mode connect on
PTC TNCs.

Examples:

```
C G8BPQ-7
C 1 G8BPQ-7
C 1 GB7BPQ VIA G8BPQ
C !MB7NRR-7
C BBS@G8BPQ
```

<a id="nc"></a>
### `NC` *(abbr: 2)*

Identical to [`CONNECT`](#connect). Provided so that a single character
beginning with `N` (for example `N`) does not collide with a connect
attempt.

<a id="attach"></a>
### `ATTACH` *(abbr: 1)*

Source: `ATTACHCMD` in `Cmd.c:4283`.

```
ATTACH <port> [<args>...]
```

Allocates one of the multi-stream (PACTOR, ARDOP, VARA, WINMOR, KAM,
SCS, Telnet) sessions on the named external port and connects this
session to it. Returns `Invalid Port` if the port is not a multi-stream
port, `Error - TNC Not Ready` if the helper is offline, or
`Sorry, you are not allowed to use this port` if `PERMITGATEWAY` is not
set and the session is not authenticated.

After a successful attach you can issue the radio-side connect (e.g.
`C M0XXX`) on the same session.

<a id="bye"></a>
### `BYE`, `QUIT` *(abbr: 1)*

Source: `BYECMD` in `Cmd.c:1156`.

Disconnects the current node session. Any cross-linked partner
session is also closed.

On a Telnet client, the underlying TCP socket is *kept* — the user
sees `*** Disconnected from Stream N` followed by
`Disconnected from Node - Telnet Session kept`, and the connection
stays alive for further use without re-prompting (you can keep
issuing commands; they execute against the same telnet session).
To fully close, the client must close the TCP socket itself.

<a id="password"></a>
### `PASSWORD` *(abbr: 8)*

Source: `PWDCMD` in `Cmd.c:1232`.

```
PASSWORD                 ← request a 5-digit challenge
PASSWORD <5 chars>       ← respond to a previous challenge
```

When entered with no arguments the node returns five space-separated
digits, each of which is the 1-based offset of a character in the
configured `PWTEXT` to which the user must respond. Re-issue the
command with the corresponding five characters concatenated together
to authenticate. A `Secure_Session` (BPQ host, sysop login) is
authenticated automatically and replies `OK`.

Authentication is required for every command listed earlier in the
`COMMANDS[]` table than `PASSWORD` itself — i.e. the sysop port-control,
switch-global and action commands.

<a id="question"></a>
### `?` *(abbr: 1)*

Source: `CMDQUERY` in `Cmd.c:3961`.

Lists the currently configured application names followed by the
hard-coded user command list (`CONNECT BYE INFO NODES PORTS ROUTES
USERS MHEARD`). Use [`HELP`](#help) for the full operator manual.

<a id="help"></a>
### `HELP` *(abbr: 1)*

Source: `HELPCMD` in `Cmd.c:6300`.

Reads `NodeHelp.txt` from `BPQDirectory` and sends it to the user one
line at a time, normalising line endings. If the file is missing the
node replies `Help file not found`.

<a id="info"></a>
### `INFO` *(abbr: 1)*

Source: `CMDI00` in `Cmd.c:1137`. Prints the configured `INFOMSG`
(`INFOMSG = ...` in `bpq32.cfg`).

<a id="version"></a>
### `VERSION` *(abbr: 1)*

Source: `CMDV00` in `Cmd.c:1146`. Prints `Version <VersionString>`,
appending `(64 bit)` on 64-bit builds.

<a id="nodes"></a>
### `NODES` *(abbr: 1)*

Source: `CMDN00` in `Cmd.c:3440`.

```
NODES                  list aliased nodes (4 columns)
NODES C                list sorted by callsign (otherwise alias order)
NODES T                list with RTT/Frames detail (INP3 nodes)
NODES *                include hidden (#) nodes
NODES <pattern>[*?]    wildcard search on alias or callsign
NODES >NN              only nodes whose best route is ≥ NN quality
NODES <call>           detail for one node (routes, RTT, INP3 srtt)
NODES VIA <call>       list nodes reachable via that neighbour
NODES ADD ALIAS:CALL Q NEIGHBOUR PORT [!]   (sysop) add a static route
NODES DEL <call>       (sysop) delete a node
NODES DEL ALL          (sysop) delete every learned node
```

The `ADD` and `DEL` forms require sysop status. `ADD` rejects a
quality below `MINQUAL`. A trailing `!` on `ADD` marks the route as
locked.

Detail output for one node looks like:

```
Routes to: HOME:M0LTE-7 RTT=1.23 FR=42 B 5
> 192 6 1 G8BPQ-7
  150 4 2 GB7BPQ
```

<a id="routes"></a>
### `ROUTES` *(abbr: 1)*

Source: `CMDR00` in `Cmd.c:1967`.

```
ROUTES                 list all neighbours (compact)
ROUTES V               verbose (frames/retries/RTT/INP3 srtt)
ROUTES V <port>        verbose, single port
ROUTES <call> <port> <quality> [!]   (sysop) add or set quality
ROUTES <call> <port> !                (sysop) toggle locked flag
ROUTES <call> <port> Z                (sysop) zero frame/retry counts
```

Compact output columns: active marker (`>`), port, neighbour, quality,
node count, lock flag (`!`/`!!`/`!!!`).

<a id="links"></a>
### `LINKS` *(abbr: 1)*

Source: `CMDL00` in `Cmd.c:1547`.

```
LINKS                          list active L2 links
LINKS RESET <dest> <src> <port>  (sysop) DISC and tear down a link
```

Output line example: `M0LTE -7G8BPQ S=5 P=1 T=0 V=2.2 Q=0`. Where the
queue size `Q` exceeds 16, internal debug fields (frame slots, NS, OWS)
are appended automatically to aid diagnosis.

<a id="users"></a>
### `USERS` *(abbr: 1)*

Source: `CMDS00` in `Cmd.c:1631`.

Prints the L4 circuit table including buffer count (`QCOUNT`). Each
line shows uplink and downlink halves of crosslinks separated by
`<-->` (connected) or `<~~>` (disconnecting). Closing-only sessions
are shown as `(Closing)`.

<a id="ports"></a>
### `PORTS` *(abbr: 1)*

Source: `CMDP00` in `Cmd.c:1703`.

```
PORTS         list configured ports and descriptions
PORTS E       extended view including state (Open / Closed / In Use / Stopped)
```

The extended view recognises KISS, loopback, telnet, and external
hardware (ARDOP, VARA, WINMOR, MPSK, FLDIGI, FreeData, KAM, SCS,
WINRPR, etc.).

<a id="streams"></a>
### `STREAMS` *(abbr: 6)*

Source: `CMDSTREAMS` in `Cmd.c:6588`.

Lists all in-use BPQ host streams with RX/TX/MON counts, the
application bitmask (or number when only one bit is set), the flag
byte, the connected callsign and the host program name. Useful for
tracking what BBS, chat, mail or third-party host is bound to which
slot.

<a id="stats"></a>
### `STATS` *(abbr: 1)*

Source: `CMDSTATS` in `Cmd.c:1300`.

```
STATS         system summary plus all ports (max 7 wide)
STATS S       system summary only
STATS <port>  port-only summary (single port view)
```

System summary covers uptime, semaphore gets/releases/clashes, buffer
high/low/wait counts, known nodes, and L3/L4 frame totals. Per-port
counters include digipeated frames, frames heard / for-us / sent,
timeouts, REJ, out-of-sequence, resequenced, underruns, RX overruns,
CRC errors, FRMRs and an `Active(TX/Busy) %` snapshot.

<a id="mheard"></a>
### `MHEARD` / `MH` / `MHL` / `MHU` / `MHV` / `MHLV` / `MHUV` *(abbr: 1–3)*

Source: `MHCMD` in `Cmd.c:4000`.

```
MH <port> [<pattern>]   list heard stations on port (default UTC, brief)
MHL <port>              local time format
MHU <port>              UTC time format (default)
MHV <port>              verbose: callsign, time, packets, "via DIGI"
MHLV / MHUV <port>      verbose with local / UTC time
MH <port> CLEAR         (sysop) clear heard list and persist
```

Returns `MHEARD not enabled on that port` if the port has no MH array.
The optional pattern filters the displayed callsign substring (the `*`
suffix on a digipeated call is preserved).

<a id="nrr"></a>
### `NRR` *(abbr: 1)*

Source: `NRRCMD` in `Cmd.c:4213`.

```
NRR <call|alias>
```

Sends a NET/ROM Record-Route trace to the chosen destination. Returns
`OK` once dispatched, `Not found` if neither alias nor callsign is in
the node table. The response (route list with hop callsigns) is
delivered later by the network as a normal NET/ROM frame.

<a id="paclen"></a>
### `PACLEN` *(abbr: 3)*

Source: `CMDPAC` in `Cmd.c:1163`.

```
PACLEN              show this session's L4 packet length
PACLEN <30..255>    set this session's L4 packet length
```

Out-of-range values are silently ignored.

<a id="idletime"></a>
### `IDLETIME` *(abbr: 4)*

Source: `CMDIDLE` in `Cmd.c:1185`.

```
IDLETIME             show this session's idle timeout (seconds)
IDLETIME <60..900>   set this session's idle timeout
```

<a id="l4t1"></a>
### `L4T1` *(abbr: 2)*

Source: `CMDT00` in `Cmd.c:1207`.

```
L4T1               show this session's L4 retry timeout
L4T1 <secs>        set timeout (must be > 20)
```

Note that this is the *per-session* L4 timeout. The global default is
[`L4TIMEOUT`](#switch-globals).

<a id="listen"></a>
### `LISTEN` / `LIS` *(abbr: 3)*

Source: `LISTENCMD` in `Cmd.c:2115`.

```
LISTEN <port>[, <port>...]    monitor unproto on the listed ports
LISTEN OFF                    stop listening
```

Refuses to listen on the same port the session is already connected
on, on non-AX.25 ports (`PROTOCOL == 10`, no `UICAPABLE`) and on
`L3ONLY` ports. Once active, [`CQ`](#cq) becomes available *if* you are
listening on exactly one port.

<a id="cq"></a>
### `CQ` *(abbr: 2)*

Source: `CQCMD` in `Cmd.c:2321`.

```
CQ [VIA <digi>[,<digi>...]] [text]
```

Builds a UI frame with destination `CQ`, the configured user callsign
as origin (SSID bits inverted) and the supplied text payload. Up to
seven digipeaters may be specified. You must first issue
[`LISTEN`](#listen) on a single port; otherwise the node responds
`You must enter LISTEN before calling CQ` or
`You can't call CQ if LISTENing on more than one port`.

<a id="unproto"></a>
### `UNPROTO` *(abbr: 2)*

Source: `UNPROTOCMD` in `Cmd.c:2199`.

```
UNPROTO <port> <addr>[,<digi>...]
```

Switches the session into UI transmit mode towards `<addr>`. Every
subsequent line is sent as a UI frame on the chosen port until the
session is exited with `Ctrl-Z` or `/EX`. Refuses non-AX.25 ports and
`L3ONLY` ports.

<a id="ping"></a>
### `PING` *(abbr: 2)*

Source: `PING` in `IPCode.c:4741`.

```
PING <a.b.c.d>
```

Sends an ICMP echo request via the BPQ IP gateway. Replies `OK`,
`No Route to Host`, `Invalid Address` or `IP Gateway is not enabled`.
The payload contains a fixed marker (`*BPQPINGID*`) and a timestamp so
incoming replies can be correlated with the issuing session.

<a id="arp"></a>
### `ARP` *(abbr: 3)*

Source: `SHOWARP` in `IPCode.c:4799`.

```
ARP             list ARP entries (IP, MAC or AX.25 path, interface, type, age, lock)
ARP CLEAR       (sysop) flush every non-locked entry, persist via SaveARP()
```

<a id="nat"></a>
### `NAT` *(abbr: 3)*

Source: `SHOWNAT` in `IPCode.c:4894`. Lists the BPQ IP-gateway NAT
table (`origIP to mappedIP [via TAP]`).

<a id="iproute"></a>
### `IPROUTE` *(abbr: 3)*

Source: `SHOWIPROUTE` in `IPCode.c:4953`.

```
IPROUTE                 list every route (sorted)
IPROUTE <substring>     filter rows whose printed form contains the substring
```

Each row shows `network/prefix frames [gateway|encap dest] type metric
RIPtimeout [Locked]`.

<a id="axresolver"></a>
### `AXRESOLVER` *(abbr: 3)*

Source: `AXRESOLVER` in `Cmd.c:5398`.

```
AXRESOLVER <port>
```

Lists the AXIP resolver table for the named port: `<call> = <host> <udp
port> = <ip> <flags>`. Flags are `B` broadcast, `C` TCP connected, `A`
auto-added.

<a id="axmheard"></a>
### `AXMHEARD` *(abbr: 3)*

Source: `AXMHEARD` in `Cmd.c:5488`.

```
AXMHEARD <port>
```

Lists the AXIP heard table for an AXIP port (callsign, address,
protocol, port, last heard, optional `K` for keepalive).

<a id="agwstatus"></a>
### `AGWSTATUS` *(abbr: 3)*

Source: `SHOWAGW` in `AGWAPI.c:406`. Lists the AGWPE-emulation
sockets and their per-call connection state. Returns
`AGW Interface is not enabled` if no AGW listener is configured.

<a id="telstatus"></a>
### `TELSTATUS` *(abbr: 3)*

Source: `SHOWTELNET` in `TelnetV6.c:7122`.

```
TELSTATUS <port>
```

Shows the CMS state and the current Telnet sockets, identifying HTTP,
WebSocket, DRATS, login-in-progress and authenticated sessions
(callsign and BPQ host stream).

<a id="rhp"></a>
### `RHP` *(abbr: 3)*

Source: `RHPCMD` in `RHP.c:807`. Lists Remote Host Protocol sessions
(BPQ stream, local / remote callsigns, handle, sequence, busy flag).

<a id="qtsm"></a>
### `QTSM` *(abbr: 4)*

Source: `QTSMCMD` in `Cmd.c:6460`.

```
QTSM <port>
```

Reports the modem name and centre frequency for a KISS port that has
QtSoundModem statistics. Returns `Error - Port N is not a KISS port`
or `Error - Port N has no QtSM information` otherwise.

<a id="aprs"></a>
### `APRS` *(abbr: 2)*

Source: `APRSCMD` in `APRSCode.c:8010`. The default action (no
sub-command) prints the APRS heard list.

```
APRS                          list heard APRS stations (UI digipeated)
APRS <port>                   list filtered by port
APRS <port> <pattern>         list filtered by port and substring
APRS ?                        list available sub-commands
APRS STATUS                   show IGate status (enabled / connected)
APRS MSGS                     list received APRS messages
APRS SENT                     list outstanding outbound messages
APRS BEACON                   (sysop) request two beacon transmissions
APRS SEND <call> <text...>    (sysop) inject a message; uppercased text is
                              re-translated from the original-case copy
APRS ENABLEIGATE              (sysop) enable the IS-IGate
APRS DISABLEIGATE             (sysop) disable the IS-IGate
APRS RECONFIG                 (sysop) re-read the APRS section of the config
```

<a id="wl2ksysop"></a>
### `WL2KSYSOP` *(abbr: 5, sysop)*

Source: `WL2KSYSOP` in `Cmd.c:5558`. Queries the Winlink WL2K sysop
record for the configured `WL2KCall` and prints it. With `SET` and a
not-yet-existing record it submits the local fields back to
`api.winlink.org`. Returns `Winlink reporting is not configured` if
`WL2KCall` is empty.

<a id="radio"></a>
### `RADIO` *(abbr: 3)*

Source: `RADIOCMD` in `Cmd.c:4184`. Forwards the (case-preserving)
command tail to `Rig_Command()`. Returns the rig-controller's reply
verbatim, or its error message on failure. Examples:

```
RADIO 1 7050000
RADIO 1 PTT ON
```

<a id="uz7ho"></a>
### `UZ7HO` *(abbr: 5)*

Source: `UZ7HOCMD` in `Cmd.c:6389`.

```
UZ7HO <port> FREQ <hz>      set centre frequency on a UZ7HO modem
UZ7HO <port> MODEM <name>   switch modem
UZ7HO <port> FLAGS <bits>   set per-channel flags
```

Errors are `Error - <port> is not UZ7HO port` or
`Invalid UZ7HO Command (not Freq Modem or FLAGS)`.

---

## Sysop reference

<a id="port-parameters"></a>
### Port parameters (`CMD PORT [VALUE]`)

Source: `PORTVAL` in `Cmd.c:553`. All entries listed in the
[Port parameters](#sysop--port-parameters-portparm-port-value) quick
table behave identically:

```
TXDELAY 1               show TXDELAY for port 1
TXDELAY 1 30            set TXDELAY for port 1 to 30, print "TXDELAY  was X now 30"
```

Invalid port returns `Invalid parameter`. `EXTRESTART` requires the
target port to be an external port; otherwise the node returns
`Not an external port`. `VALIDCALLS` is a thin wrapper around
`PORTVAL` that prints the configured `PERMITTEDCALLS` array; without
permitted calls it returns the configured `NOVALCALLS` text.

<a id="extrestart"></a>
### `EXTRESTART` *(abbr: 10, sysop)*

```
EXTRESTART <port>      restart the external (TNC helper) port
```

Like `STARTPORT` for external ports — sets the port-control
`EXTRESTART` byte; the timer thread picks it up and recycles the
helper.

<a id="switch-globals"></a>
### Switch globals (`CMD [VALUE]`)

Source: `SWITCHVAL` (8-bit) and `SWITCHVALW` (16-bit) in `Cmd.c:668`
and `Cmd.c:713`. Each entry in the
[switch-globals quick table](#sysop--switch-globals) prints
`<NAME> <value>` when called bare and
`<NAME> was X now Y` when given a new value.

`NODESINT` additionally resets `L3TIMER` to the new value so the next
nodes broadcast happens immediately.

<a id="savenodes"></a>
### `SAVENODES` *(abbr: 8, sysop)*

Source: `SAVENODES` in `Cmd.c:429`. Calls `SaveNodes()`
(`CommonCode.c:3060`), which writes both the NET/ROM destinations and
the neighbour routes to a single `BPQNODES.dat` file in `BPQDirectory`;
replies `OK`.

<a id="savemh"></a>
### `SAVEMH` *(abbr: 6, sysop)*

Source: `SAVEMHCMD` in `Cmd.c:419`. Persists every port's heard list
via `SaveMH()`.

<a id="pollnodes"></a>
### `POLLNODES` *(abbr: 8, sysop)*

Source: `POLLNODES` in `Cmd.c:307`.

```
POLLNODES <port>
```

Sends a NET/ROM nodes-poll UI (`0xFE`) on the chosen port carrying
this node's six-character alias. Refuses ports with
`PORTQUALITY == 0` or `INP3ONLY` set. On a VARA port the poll is
delivered via `SendVARANetromNodes()` so it reaches the modem.

<a id="sendnodes"></a>
### `SENDNODES` *(abbr: 8, sysop)*

Source: `SENDNODES` in `Cmd.c:395`.

```
SENDNODES         broadcast on every port
SENDNODES <port>  broadcast on a specific port
```

<a id="sendrif"></a>
### `SENDRIF` *(abbr: 7, sysop)*

Source: `SENDRIF` in `Cmd.c:366`.

```
SENDRIF <port> <neighbour>
```

Delivers an INP3 RIF (`sendAlltoOneNeigbour`) to a single neighbour
discovered via `FindNeighbour`. Returns `Route not found` otherwise.

<a id="reboot"></a>
### `REBOOT` *(abbr: 6, sysop)*

Source: `REBOOT` in `Cmd.c:464`. Calls `Reboot()` to restart the host
machine.

<a id="restart"></a>
### `RESTART` *(abbr: 7, sysop)*

Source: `RESTART` in `Cmd.c:480`. Calls `Restart()` to restart
LinBPQ / BPQ32 itself.

<a id="restarttnc"></a>
### `RESTARTTNC` *(abbr: 10, sysop)*

Source: `RESTARTTNC` in `Cmd.c:496`.

```
RESTARTTNC <port>
```

Restarts the helper program (`PATH ...` from the configured TNC
section) for the named port. Returns `PATH not defined so can't
restart TNC` if no helper is configured, or `Restart <path> Failed` if
the relaunch fails.

<a id="rigreconfig"></a>
### `RIGRECONFIG` *(abbr: 8, sysop)*

Source: `RIGRECONFIG` in `Cmd.c:449`. Re-runs `ProcessConfig()` and
sets `RigReconfigFlag`; the rig-control thread picks the new config up.

<a id="telreconfig"></a>
### `TELRECONFIG` *(abbr: 4, sysop)*

Source: `RECONFIGTELNET` in `TelnetV6.c:6937`.

```
TELRECONFIG <port>           reconfig only for a Telnet port
TELRECONFIG <port> ALL       full restart (uses EXTRESTART)
TELRECONFIG <port> USERS     reload only the user database
```

Reading users does not free old user records (active sessions still
hold pointers) but rebinds new ones from disk.

<a id="stopport"></a>
### `STOPPORT` *(abbr: 4, sysop)*

Source: `STOPPORT` in `Cmd.c:5831`. Stops a port. For ports that
register a `PORTSTOPCODE` it calls that handler; for raw KISS serial
ports it calls `CloseKISSPort`. Returns `Not a KISS Port`,
`Not a serial port` or `Not first port of a Multidrop Set` when
applicable.

<a id="startport"></a>
### `STARTPORT` *(abbr: 5, sysop)*

Source: `STARTPORT` in `Cmd.c:5915`. Inverse of `STOPPORT` — calls
`PORTSTARTCODE` or `OpenConnection` and clears `PortStopped`.

<a id="stopcms"></a>
### `STOPCMS` *(abbr: 7, sysop)*

Source: `STOPCMS` in `Cmd.c:5710`.

```
STOPCMS <port>
```

Disables CMS forwarding on a Telnet port (`CMS = 0`, `CMSOK = FALSE`).
Returns `Not a Telnet Port` for the wrong port type.

<a id="startcms"></a>
### `STARTCMS` *(abbr: 8, sysop)*

Source: `STARTCMS` in `Cmd.c:5771`. Enables CMS and immediately runs
`CheckCMS(TNC)`.

<a id="stoproute"></a>
### `STOPROUTE` *(abbr: 9, sysop)*

Source: `STOPROUTE` in `Cmd.c:6007`.

```
STOPROUTE <port> <neighbour>
```

Marks the route stopped, decays its NET/ROM and INP3 routes, sends a
DISC (or closes the TCP connection for NET/ROM-TCP routes) and bumps
`BCTimer` so it will not be retried for a long time. Replies
`Route not active` if there is no live link.

<a id="startroute"></a>
### `STARTROUTE` *(abbr: 10, sysop)*

Source: `STARTROUTE` in `Cmd.c:6079`. Re-enables a previously
`STOPROUTE`d neighbour by clearing `Stopped` and `BCTimer`.

<a id="kiss"></a>
### `KISS` *(abbr: 4, sysop)*

Source: `KISSCMD` in `Cmd.c:6133`.

```
KISS <port> <byte> [<byte>...]
```

Sends KISS-encoded raw bytes (decimal) to a KISS-like port. Useful for
poking TNC parameters that BPQ does not expose directly. Returns
`Not a KISS Port` for non-KISS ports.

<a id="findbuffs"></a>
### `FINDBUFFS` *(abbr: 4, sysop)*

Source: `FINDBUFFS` in `Cmd.c:6216`. Calls `FindLostBuffers()` and
notes that the report has been written to the debug log
(DebugView on Windows, syslog on Linux).

<a id="getportctext"></a>
### `GETPORTCTEXT` *(abbr: 9, sysop)*

Source: `GetPortCTEXT` in `CommonCode.c:4898`. Re-reads every
`Port<n>CTEXT.txt` file from `BPQDirectory`, normalising line endings,
and reports the list of ports that picked up new text.

<a id="validcalls"></a>
### `VALIDCALLS` *(abbr: 5, sysop)*

```
VALIDCALLS <port>
```

Lists the `PERMITTEDCALLS` array for a port; if empty, prints the
configured `NOVALCALLS` text.

<a id="exclude"></a>
### `EXCLUDE` *(abbr: 4, sysop, Windows build)*

Source: `ListExcludedCalls` in `Cmd.c:6251`. Only present in builds
compiled with `EXCLUDEBITS`.

```
EXCLUDE                show the exclusion list
EXCLUDE <call>         add a call to the list (max 10 entries)
EXCLUDE Z              clear the list
```

Excluded callsigns cannot issue [`CONNECT`](#connect).

<a id="dump"></a>
### `DUMP` *(abbr: 4, sysop)*

Source: `DUMPCMD` in `Cmd.c:439`. Calls `WriteMiniDump()` (Windows
build) to write a process minidump for support analysis.

<a id="application-commands"></a>
### Application commands (`BBS`, `CHAT`, `MAIL`, ...)

Source: `APPLCMD` in `Cmd.c:990`. Each `APPLICATION` line in
`bpq32.cfg` produces an entry in the dispatch table that, when typed
at the prompt, attaches the session to that application's host
stream. Behaviour:

- If an `ALIAS` is configured for the application the alias text is
  re-injected as a node command (the session is briefly elevated to
  `Secure_Session` so a Telnet outward connect can succeed).
- If `CMD_TO_APPL` is set in the application flags the typed command
  line is forwarded to the application as the first packet.
- If `MSG_TO_USER` is set the node prints `Connected to <APP>` to the
  user; otherwise the application banner takes over.
- If all of the application's slots are busy the user receives
  `Sorry, All <APP> Ports are in use - Please try later`. If no slots
  are configured, `Sorry, Application <APP> is not running - Please
  try later`.

A trailing `S` argument (`BBS S`) sets the *stay* flag — the user is
returned to the node prompt rather than disconnected when the
application closes the stream.

---

## Host-protocol pseudo-commands

These dispatch-table entries are not for human use. They are token
strings that gateway / host programs send so the node will react in a
defined way; they appear here only because they are real entries in
the `COMMANDS[]` table and show up in command traces.

<a id="linked"></a>
### `*** LINKED` *(abbr: 10)*

Source: `LINKCMD` in `Cmd.c:3251`.

```
*** LINKED to <call>
```

The magic string that gateway host programs (BBS, mail, chat
front-ends that sit in front of the node) inject at the prompt to
tell the node the real callsign of the user behind their session. It
overrides the L4 user callsign for the rest of the connection so that
subsequent commands appear to come from `<call>`.

Permitted only when:

- `LINKEDFLAG = Y` — any session may issue it; or
- `LINKEDFLAG = A` — only BPQ-host or already-authenticated
  (`Secure_Session` / sysop-password) sessions may issue it.

Returns `OK` on success, the password prompt otherwise.

<a id="flmsg"></a>
### `..FLMSG` *(abbr: 7)*

Source: `FLMSG` in `Cmd.c:6228`.

The magic string that the FLMSG Telnet client sends when it first
connects. The handler simply disconnects the session
(`CLOSECURRENTSESSION`); the dispatch-table entry exists so the node
recognises the FLMSG handshake instead of replying with
`Invalid command`.
