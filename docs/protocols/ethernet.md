# BPQ Ethernet

`BPQETHER` carries AX.25 frames inside Ethernet frames using
EtherType `0x08FF` — turning your LAN into a glorified packet
bus between BPQ nodes (and any other AX-over-Ethernet
implementation that speaks the same EtherType).

The wire format is identical between the Windows and Linux
builds; only the kernel-side mechanism differs.  Both use the
same ADAPTER / TYPE / RXMODE / TXMODE / PROMISCUOUS keyword set.

!!! note "Upstream and source"
    Re-presentation of John Wiseman's [BPQ Ethernet][upstream]
    page.  Linux side cross-checked against `linether.c`
    (raw-socket implementation, config parser); Windows side
    against `bpqether.c` (WINPCAP-based) and `xbpqether.c`.

[upstream]: https://www.cantab.net/users/john.wiseman/Documents/BPQ%20Ethernet.htm

## Wire format

```
| Eth dst (6) | Eth src (6) | EtherType (2) | …optional 3 bytes (RLI)… | length (2 LE) | AX.25 frame | … |
```

Two minor variants live under EtherType `0x08FF`:

- **BPQ format** — used by ODIDRV, the Linux kernel's old AX.25
  network device, and BPQ32's `bpqether.dll`.  No extra header
  bytes; length follows the EtherType.
- **RLI format** — used by W0RLI's SNOS and the BPQENET
  interface.  Three extra bytes (`00 00 41`) between the
  EtherType and the length.

The `RXMODE` / `TXMODE` keywords pick which variant LinBPQ uses
on each direction; the EtherType (`0x08FF`) is the same either way.

## Linux side

Linux LinBPQ implements BPQ Ethernet directly with a `PF_PACKET`
raw socket — no `libpcap` or kernel module needed.  `linether.c`
opens `socket(AF_PACKET, SOCK_RAW, htons(ETH_P_BPQ))` and
binds it to the configured interface.

```ini
PORT
 ID=BPQ Ethernet
 TYPE=EXTERNAL
 DRIVER=BPQETHER
 QUALITY=200
 MAXFRAME=7
 PACLEN=236
 CONFIG
 ADAPTER eth0
 TYPE 08FF
 RXMODE BPQ
 TXMODE BPQ
ENDPORT
```

Capabilities: raw sockets need `CAP_NET_RAW` on the binary —
the standard setcap line from [Getting started][gs] handles it.

[gs]: ../getting-started/index.md

Linux notes:

- `ADAPTER` takes a Linux interface name (`eth0`, `enp4s0`, etc.).
  The PCAP-style escaped-UID form Windows uses isn't applicable.
- `bpqether` is **not built on FreeBSD or macOS** (`#ifndef
  FREEBSD / MACBPQ` guards in `linether.c`); the makefile
  drops it on those platforms.
- The companion driver `xbpqether.c` (mostly DOS-era) isn't
  used on Linux.

## Windows side

The Windows `BPQEther.dll` driver wraps [WinPcap][winpcap]
(or its successor [Npcap][npcap]) to do the same job.  Same
config keyword set, but `ADAPTER` takes a Windows escaped
device UID rather than an interface name:

[winpcap]: https://www.winpcap.org/
[npcap]: https://nmap.org/npcap/

```ini
PORT
 ID=BPQ Ethernet
 TYPE=EXTERNAL
 DRIVER=BPQETHER
 QUALITY=200
 CONFIG
 ADAPTER \Device\NPF_{ECDB1154-982B-48D3-A394-785AC42588E3}
 TYPE 08FF
ENDPORT
```

Use the bundled `bpqadapters.exe` utility in the BPQ32 install
directory to list candidate adapters and copy the right UID
into `bpq32.cfg`.

## CONFIG block keywords

| Keyword | Effect |
|---|---|
| `ADAPTER <id>` | Linux: interface name (`eth0`).  Windows: escaped device UID. |
| `TYPE <hex>` | EtherType in hexadecimal (default `08FF`). |
| `RXMODE <BPQ|RLI>` | Inbound framing variant.  Default `BPQ`. |
| `TXMODE <BPQ|RLI>` | Outbound framing variant.  Default `BPQ`. |
| `PROMISCUOUS <0|1>` | If `1`, put the interface in promiscuous mode (lets you receive frames not addressed to your MAC). |
| `DEST <mac>` | Destination MAC for outbound frames.  Default broadcast. |
| `SOURCE <mac>` | Source MAC.  Default the interface's own MAC. |

## Use cases (ish)

In practice BPQETHER is useful for two things:

1. **Linking BPQ instances on the same LAN** without going
   through TCP/IP — slightly lower latency, no IP-stack involvement.
   Niche; AX/IP-UDP is usually fine.
2. **Connecting to legacy AX.25-over-Ethernet hardware** (old
   Z80-based SNOS boxes, ODIDRV-based DOS systems).  Increasingly
   rare.

For new deployments [AX/IP over UDP][axip] is the better default —
it routes between hosts, traverses NAT, and doesn't need raw
socket capabilities.

[axip]: axip.md
