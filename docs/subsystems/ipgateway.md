# IP gateway

LinBPQ can bridge IP traffic between an Ethernet interface and
IP-over-AX.25 packet links — turning the node into a gateway
that lets a TCP/IP stack on the PC side see other 44/8 hosts on
the radio side, and vice versa.  This is the original *amateur
TCP/IP* feature; in 2026 it's mostly used by
[AMPRNet][amprnet] gateway operators and people doing
old-school KA9Q / NOS interop.

[amprnet]: https://www.ampr.org/

!!! warning "Hardware-and-network-dependent"
    This page documents the cfg surface and command set
    accurately.  End-to-end behaviour depends on having a real
    Ethernet interface, a 44/8 IP allocation, and a peer node
    you can route to over RF.  If you find this page disagrees
    with what LinBPQ actually does, please open an issue.

!!! note "Upstream and source"
    Re-presentation of John Wiseman's [IP Gateway Feature][upstream]
    page.  Cross-checked against `IPCode.c`.

[upstream]: https://www.cantab.net/users/john.wiseman/Documents/IPGateway.html

## What it does

- **Bridges IP-over-AX.25** to IP-over-Ethernet.
- **Builds ARP tables dynamically** from monitored frames, plus
  whatever you configure statically.
- **NAT** between 44/8 amateur addresses and your local LAN
  range — handy if your PC doesn't speak 44/8 directly.
- **AMPRNet IPIP tunnelling** with RIP44 dynamic routes — for
  Internet-mediated links to other amateur sites.
- **Limited SNMP** for MRTG-style monitoring of bytes-in /
  bytes-out per port.

## Enabling

A single `IPGATEWAY ... ****` block in `bpq32.cfg`:

```ini
IPGATEWAY
 ADAPTER eth0
 IPADDR 44.131.56.1
 IPNETMASK 255.255.255.248
 IPPORTS 1,3,7

 NAT 44.131.56.2 192.168.1.101

 ARP 44.131.56.6 G8BPQ-8 1 D
 ARP 44.131.11.1 GM8BPQ-7 1 D
 ROUTE 44.131.11.0/29 44.131.11.1

 ENABLESNMP
****
```

The block ends with `****` (four asterisks) on a line by itself.

## Linux specifics

- **Adapter**: `ADAPTER eth0` (or whatever `ip link show` calls
  your wired interface).
- **TAP for local traffic**: linbpq creates a TAP device on the
  fly for traffic destined for the host itself, and uses libpcap
  for everything else.  No need to predefine a TAP.
- **Capabilities required**: building a TAP and writing to a raw
  socket needs `CAP_NET_ADMIN` and `CAP_NET_RAW` — the standard
  setcap line from [Getting started][gs] covers this.

[gs]: ../getting-started/index.md

## CONFIG block keywords

### Required

| Keyword | Effect |
|---|---|
| `ADAPTER <name>` | Linux: interface name (`eth0`).  Windows: encoded UID — use `bpqadapters.exe` to find. |
| `IPADDR <addr>` | The gateway's IP on your LAN.  Must be from your AMPRNet allocation and *distinct from the PC's address* unless you've gone all-in on 44/8 for the LAN. |
| `IPNETMASK <mask>` | Netmask for the AMPRNet allocation.  Alternative form: `IPADDR 44.131.56.0/29`. |
| `IPPORTS <list>` | Comma-separated list of LinBPQ port numbers that carry IP-over-AX.25. |

### Routing and addressing

| Keyword | Effect |
|---|---|
| `ARP <ip> <call> <port> <mode>` | Static ARP entry.  Mode is `D` (datagram, UI) or `V` (virtual circuit, connected mode). |
| `ROUTE <net>/<mask> <gw> [T]` | Static IP route.  `T` flag = tunnel via the AMPRNet IPIP gateway. |
| `NAT <amp-addr> <lan-addr>` | Translate AMPRNet address to LAN address — lets a 192.168 host be reachable from 44/8. |
| `44ENCAP <virtual-ip>` | Enable AMPRNet IPIP tunnel processing and RIP44 dynamic routes; the virtual IP is the tunnel endpoint, ideally in a DMZ. |
| `NODEFAULTROUTE` | Suppress the auto-installed `44/8 → tap` route.  Useful when you only want to gateway a small slice. |

### Monitoring

| Keyword | Effect |
|---|---|
| `ENABLESNMP` | Open the SNMP server on UDP/161.  Pair with `SNMPPORT=` at top level for an alternative listening port. |

## Sysop commands

These run from the node prompt and are gated on the IP gateway
being enabled — without `IPGATEWAY`, they reply
`IP Gateway is not enabled`:

| Command | Effect |
|---|---|
| `PING <addr>` | ICMP-style ping to `<addr>` (numeric only, not hostnames). |
| `ARP` | Print the full IP-over-AX.25 ARP table. |
| `IPR [<prefix>]` | Print the IP routing table; optional prefix filter. |
| `NAT` | Print active NAT translations. |

## SNMP

The SNMP server answers a small set of OIDs:

| OID | Value |
|---|---|
| `sysName.0` | The node call (`NODECALL` from cfg). |
| `sysUpTime.0` | Time since linbpq started, in centiseconds. |
| `ifInOctets`, `ifOutOctets` (per IP-port) | Per-port byte counters. |

Unknown OIDs are silently dropped — same shape as the SNMP
spec recommends.  See [`IPCode.c:5365`][ipsnmp] for the
implementation.

[ipsnmp]: https://github.com/M0LTE/linbpq/blob/master/IPCode.c

## When this page goes wrong

If you've configured the gateway and `IPR` shows your routes but
nothing actually flows, the usual causes are:

- **Linux capabilities missing** — `getcap ./linbpq` should show
  `cap_net_admin,cap_net_raw,cap_net_bind_service+ep`.
- **Adapter name doesn't match** — `ip link` after boot to confirm
  the interface still has the name in `ADAPTER`.
- **Conflicting host route** — host already has a `44.0.0.0/8`
  route somewhere; either delete it or use `NODEFAULTROUTE`.
- **Peer not in IPPORTS** — frames from a port not listed in
  `IPPORTS` get dropped by the gateway code.
