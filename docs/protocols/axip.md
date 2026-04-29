# AX.25 over IP

LinBPQ encapsulates AX.25 frames across three Internet
transports: **AXIP** (IP protocol 93), **AXUDP** (UDP), and
**AXTCP** (TCP).  In practice AXUDP is the most common because
home routers and consumer ISPs handle UDP cleanly while protocol
93 traffic gets dropped.  AXTCP exists for the case where the
remote end can't accept inbound (e.g. NAT'd public Wi-Fi).

!!! note "Upstream and source"
    Re-presentation of John Wiseman's
    [BPQAXIP Configuration page][upstream], adapted to the
    LinBPQ-specific cfg-block form (the upstream describes the
    Windows ``BPQAXIP.CFG`` external file; LinBPQ embeds the
    same content inline between ``CONFIG`` and ``ENDPORT`` in
    the main ``bpq32.cfg``).
    Driver source: ``bpqaxip.c``.

[upstream]: https://www.cantab.net/users/john.wiseman/Documents/BPQAXIP%20Configuration.htm

## Quick example

```ini
PORT
 ID=AXIP
 DRIVER=BPQAXIP
 QUALITY=200
 MINQUAL=1
 CONFIG
 UDP 10093
 BROADCAST NODES
 MAP N0PEER 127.0.0.1 UDP 10094 B
ENDPORT
```

This declares a port that:

- Listens for AXUDP traffic on UDP/10093.
- Treats `NODES` as a broadcast address (so NODES frames fan out
  to mapped peers with the `B` flag set).
- Routes any AX.25 frame addressed to a `N0PEER-*` callsign to
  `127.0.0.1:10094`, and includes that peer in NODES broadcasts
  (`B` flag).

`QUALITY=200` and `MINQUAL=1` are required for NODES propagation
to work — without them L3 (`L3Code.c`) skips this port for NODES
emission.  See [issue #4][issue4] for the full diagnosis.

[issue4]: https://github.com/M0LTE/linbpq/issues/4

## CONFIG block keywords

The keywords inside `CONFIG ... ENDPORT` are interpreted by
`bpqaxip.c::ProcessConfig`.  All optional unless noted.

### UDP

```
UDP <port>
```

Listen for AXUDP traffic on this UDP port.  Multiple `UDP` lines
are allowed — one BPQAXIP port can listen on several UDP ports
simultaneously, useful when joining several mesh networks
(GB7RDG's production cfg uses this for OARC mesh ports).

### MAP

```
MAP <callsign[-SSID]> <addr> [<protocol-options>] [B]
```

Routes outbound AX.25 frames addressed to `<callsign>` to the
internet `<addr>`.  Without an explicit SSID, the entry matches
*all* SSIDs of the call (wildcard match on the first 6 bytes).
With an SSID it's an exact 7-byte match.

`<protocol-options>` is one of:

- *(absent)* — AXIP (raw IP protocol 93).  Rarely usable on the
  open internet.
- `UDP <port>` — AXUDP.  Sends to `<addr>:<port>`.  Pair with a
  `UDP <port>` listener on the same port if you want
  bidirectional.
- `TCP-Master <port>` — AXTCP, this side originates the
  connection.
- `TCP-Slave <port>` — AXTCP, this side accepts the connection.

The trailing `B` flag declares this peer as a broadcast
recipient: NODES and ID frames fan out to it.  Without `B`, only
unicast traffic is routed.

### BROADCAST

```
BROADCAST <call>
BROADCAST NODES
BROADCAST ID
```

Declares an AX.25 call as a broadcast destination.  Frames
addressed to this call are duplicated to every `MAP` entry that
also has the `B` flag.  `BROADCAST NODES` is the standard
configuration for participating in a NET/ROM network — without
it your node won't tell its peers about its own dest list.

### MHEARD

```
MHEARD ON
```

Update the L2 MH list from received frames on this port.  Off
by default.

### Other

| Keyword | Effect | Source |
|---------|--------|--------|
| `KEEPALIVE <seconds>` (on a MAP) | Send keepalive packets at this interval to maintain NAT mappings | `bpqaxip.c::SendFrame` |
| `AUTOADDMAP` | Auto-add MAP entries for previously unknown peers | `bpqaxip.c::AutoAddARP` |
| `AUTOADDQUIET` | Same as `AUTOADDMAP` but suppress the log line | `bpqaxip.c::ProcessConfig` |
| `DONTCHECKSOURCECALL` | Skip the source-call resolution check on inbound frames | `bpqaxip.c::Checkifcanreply` |

For dropping frames from a specific call, use the **top-level**
``EXCLUDE=`` keyword in ``bpq32.cfg`` (not in this CONFIG block).
The list applies globally across drivers — see
``config.c:1104``.

## NODES propagation gotchas

A working NET/ROM-over-AX/IP setup requires three cfg knobs and
they're easy to miss:

1. **Port-block `QUALITY=` non-zero** — without it `L3Code.c`
   skips the port for NODES emission.
2. **`BROADCAST NODES`** in the CONFIG block — without it
   `NODES` isn't in `BroadcastAddresses` and frames addressed to
   it aren't fanned out.
3. **`B` flag** on every `MAP` line of a peer — without it
   `bpqaxip.c::SendFrame` treats the peer as unicast-only and
   skips broadcast deliveries.

There's also a parser gotcha:

> **The keyword=value form of `ROUTES:` is misparsed**
> ([#12][issue12]) — separator-set inconsistency in
> `config.c:1619`.  Use the comma form
> `<call>,<qual>,<port>` instead.

[issue12]: https://github.com/M0LTE/linbpq/issues/12

