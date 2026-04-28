# NET/ROM

NET/ROM is the network and transport protocol stacked on top of
AX.25.  Where AX.25 lets two stations talk, NET/ROM lets a packet
move across multiple hops, picks routes between nodes, and runs
end-to-end connections (L4 circuits) on top.

LinBPQ inherits its NET/ROM behaviour from BPQ32 and extends
it with optional INP3 routing for time-aware link-state
exchange.

## Layers

| Layer | Owns | Frames |
|---|---|---|
| L2 (AX.25) | Hop-by-hop framing, retransmit | I, RR, RNR, REJ, U-frames |
| L3 (NET/ROM) | Node-to-node routing, NODES broadcast | NODES (UI to `NODES`), L3 carrying L4 PDUs (`PID=0xCF`) |
| L4 (NET/ROM) | End-to-end circuit, retry, window | CONNECT_REQ, CONNECT_ACK, INFO, INFO_ACK, DISC_REQ |

`PID=0xCF` on an AX.25 frame says "the info field is a NET/ROM
L3 PDU" — that's how AX.25 frames carry NET/ROM.

## NODES propagation

Every `NODESINTERVAL` minutes (default 30) each port with a
non-zero `QUALITY=` emits a NODES broadcast — a UI frame to the
destination call `NODES` listing every L3 destination this node
knows about, with the best-known route's quality.

Each receiving node:

1. Parses the broadcast.
2. For each entry, applies the configured `MINQUAL`, `OBSINIT`,
   `OBSMIN` filters.
3. Updates its own NODES table.
4. The next `NODESINTERVAL` timer ticks, the receiver
   re-broadcasts a recomputed table.

### The four cfg knobs that govern propagation

| Keyword | Default | Effect |
|---|---|---|
| `NODESINTERVAL` | 30 | Minutes between broadcasts. |
| `OBSINIT` | 6 | Initial obsolescence count for a freshly-learned destination. |
| `OBSMIN` | 5 | Minimum obsolescence to *include* in our outgoing broadcasts. |
| `MINQUAL` | 150 | Quality floor for a destination to enter the NODES table. |

A destination's obsolescence ticks down each NODESINTERVAL it
*isn't* heard about; once it falls below `OBSMIN` we stop
re-advertising it; once it hits 0 we drop it.

### `QUALITY=` per port

Each PORT block sets the *default* quality assigned to nodes
heard on that port.  `QUALITY=0` parks the port at L2 only —
no NODES propagation, no L3 traffic.

`QUALADJUST=<percent>` lets a port reduce the broadcast quality
of a destination if its best route is on this same port — this
is how mesh-of-meshes setups avoid round-trip routes back to
themselves.

### NET/ROM over IP transport

NET/ROM happily runs over any L2 transport that delivers AX.25
frames — including AX/IP-UDP and AX/IP-TCP.  Worked example:
[AX/IP over UDP][axip] including the three cfg traps that
breaks NODES propagation if you miss them.

[axip]: axip.md

## L4 (transport)

NET/ROM L4 is connection-oriented like TCP — circuits set up
with a SYN-style handshake, run with windowed in-order delivery,
tear down cleanly.

Per-circuit knobs (top-level, applied to every circuit):

| Keyword | Default | Effect |
|---|---|---|
| `L4WINDOW` | 4 | Send window (frames). |
| `L4TIMEOUT` | 60 | Retry timer (s). |
| `L4DELAY` | 10 | Delayed-ACK timer (s). |
| `L4RETRIES` | 3 | Retry limit before dropping the circuit. |
| `L4Compress` | 0 | Enable L4 stream compression. |
| `L4CompMaxframe` | 3 | Frames-in-flight cap for compressed frames. |
| `L4CompPaclen` | 236 | Packet size for compressed frames. |

`MAXCIRCUITS` caps concurrent circuits (each user session takes
two — one inbound L2 → L4, one L4 → outbound).  Set to ≥ `2 ×
expected concurrent users`.

## INP3 — link-state alternative

INP3 is an optional link-state routing protocol with awareness
of round-trip time and hop count.  It runs *alongside* NODES
broadcasting; you can mix-and-match per port.

| Keyword | Effect |
|---|---|
| `MAXRTT` | Largest RTT (centiseconds) to admit to the INP3 routing table. |
| `MAXHOPS` | Largest hop count to admit. |
| `PREFERINP3ROUTES` | If `1`, INP3 routes win over NODES routes; default uses INP3 only when NODES has no route. |
| `INP3ONLY=1` (per-port) | This port doesn't accept NODES broadcasts at all. |
| `RIFInterval` | Minutes between Routing Information Frame emissions (`SENDRIF`). |

Locked-routes entries can carry `INP3=1` to enable INP3 on a
specific neighbour, or `INP3=2` for INP3 with no L2 keepalives.

## Locked routes

```
ROUTES:
GM8BPQ-5,192,2,,5,,1
G8BPQ-9,180,3
****
```

A `ROUTES:` block locks a route's quality and parameters so it
isn't supplanted by routine NODES dynamics — useful for
backbone trunks you want stable.  Full syntax in the
[Configuration reference][cfg].

[cfg]: ../configuration/reference.md

## NET/ROM over TCP

LinBPQ accepts NET/ROM L3 PDUs framed over plain TCP — useful
for site-to-site backbone links where you'd like NET/ROM
dynamics but the underlying transport is just an Internet pipe.

The wire format is `Length(2 LE) | Call(10) | PID=0xCF | L3
packet`.  Configure with `NETROMPORT=<tcp-port>` at top level
plus a locked `ROUTES:` entry whose `TCP=` field carries the
remote endpoint:

```
ROUTES:
CALL=GM8BPQ-9, PORT=2, QUALITY=192, TCP=remote.example.com:53119
****
```

Port-block `QUALITY=` still has to be non-zero for the route to
participate in NODES propagation.
