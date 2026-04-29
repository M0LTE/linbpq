# Spot-check report — Rewritten upstream pages

Pass-through of the binary / protocol-spec docs in
`docs/project/upstream.md` against the C source.  Goal: catch
subtle drift between the rewritten doc and what LinBPQ actually
does.

## Summary

| Doc | Status | Action |
|---|---|---|
| `protocols/axip.md` | One drift | Fixed in-place |
| `protocols/bpqtoagw.md` | One drift | Fixed in-place |
| `protocols/ethernet.md` | Minor caveat | Noted below; doc unchanged |
| `protocols/host-mode.md` | Clean | — |
| `subsystems/aprs.md` | Already caught by `test_doc_cfg_snippets` (port-2 fragment in harness) | — |
| `subsystems/ipgateway.md` | Clean | — |
| `protocols/pactor.md` | Not deeply checked — sample configs only | Open |
| `configuration/reference.md` | Clean (cfg-snippet test covers it) | — |

## Findings

### `protocols/bpqtoagw.md` — `IOADDR` claimed hex, parser is decimal

**Doc claim** (before fix): `IOADDR=<hex>` with `1F40 = 8000` example.

**Reality**: `config.c:2569-2574` does `atoi(rec)` on the value
after `strlop(rec, ' ')`.  `IsNumeric` only accepts decimal
digits — `1F40` would fall into the `SerialPortName` branch.
On the Windows BPQ32 build, IOADDR was historically expressed
in hex because the field was a hardware I/O port address.  On
LinBPQ for AGW use, the meaning was repurposed but the parser
stayed `atoi()`.

**Action**: changed all `IOADDR=1F40` examples to `IOADDR=8000`,
clarified the keyword table.  Committed.

### `protocols/axip.md` — `EXCLUDE` listed in CONFIG block, actually a top-level keyword

**Doc claim** (before fix): `EXCLUDE <call>` listed under the
AXIP CONFIG-block keyword table with effect "Drop frames from
this call".

**Reality**: `bpqaxip.c::ProcessConfig` does not recognise
`EXCLUDE`.  The actual keyword is `EXCLUDE=` at the top level
of `bpq32.cfg` (`config.c:1104`), populating the global
`ExcludeList` checked across multiple drivers (ARDOP, WINMOR,
VARA, FreeDATA, SCSPactor, bpqaxip).

**Action**: removed `EXCLUDE` from the AXIP CONFIG-block table,
added `AUTOADDQUIET` (which the parser does recognise but the
doc didn't list), and pointed the EXCLUDE row to the top-level
keyword instead.  Committed.

### `protocols/ethernet.md` — `PROMISCUOUS` parsed but unused on Linux

**Doc claim**: `PROMISCUOUS <0|1>` puts the interface in
promiscuous mode.

**Reality**: On Linux, `linether.c:416-422` parses the keyword
into `PCAPInfo[Port].Promiscuous`, but that field is **never
read** anywhere in the Linux codebase.  The kernel-side
behaviour is whatever the interface is in by default.  On
Windows, `bpqether.c:580-586` parses it and **does** pass it
through to `pcap_open_live` (line 409).

**Severity**: minor — the doc isn't *wrong* in general (the
keyword is accepted) but a Linux user expecting a 1 to enable
promisc will not get it.  AF_PACKET picks up frames addressed
to its EtherType filter regardless, so most use cases are
unaffected.

**Action**: not changed.  A future improvement would be to
either implement `PACKET_ADD_MEMBERSHIP` for the promiscuous
case, or drop the keyword from the Linux side of the doc.

### `subsystems/aprs.md` — Doc fragment uses `APRSPath 2=` / `Digimap 2=`

**Status**: caught by `test_doc_cfg_snippets`.  The doc fragment
references port 2 which the original single-port harness didn't
have; we extended the harness to include a second BPQAXIP loopback
port and the snippet now boots cleanly.

**Action**: harness extended (commit landed with the
cfg-snippets test); doc unchanged.

### `protocols/host-mode.md` — keyword set verified

`COMPORT`, `TYPE`, `APPLNUM`, `APPLMASK`, `APPLFLAGS`,
`CHANNELS`, `POLLDELAY` all recognised by `config.c:2857-2901`.
No drift detected.

### `subsystems/ipgateway.md` — keyword set verified

`ADAPTER`, `IPAddr`, `IPNetMask`, `IPPorts`, `NAT`, `ARP`,
`ROUTE`, `ENABLESNMP`, `UDPTunnel`, `44Encap`, `NoDefaultRoute`
all recognised by `IPCode.c:3314-3586`.  No drift detected.

### `protocols/pactor.md` — not deeply checked

The cfg-snippets test boots the fragments cleanly so the
keyword-acceptance side is solid.  Modem-driver-init wire-format
claims (KAM cmd: prompts, SCS init banners, etc.) would need
either driver-by-driver source review or a behavioural test
against the existing modem helpers — not done in this pass.

## Methodology

For each doc:

1. Read the doc end-to-end.
2. Grep the named C source for keyword acceptance (`_stricmp`)
   and behaviour claims.
3. Cross-reference any specific line numbers cited by the doc.
4. Where claims disagree with the source: fix the doc in-place
   if it's a clear factual error (decimal vs hex, wrong block
   for a keyword), or note as a caveat if it's a behavioural
   subtlety (Linux vs Windows promisc mode).
5. Where claims are accurate: no change.

The cfg-snippets test (`tests/integration/test_doc_cfg_snippets.py`)
provides ongoing protection for the keyword-acceptance side of
the doc surface — any future drift on a fenced cfg block fires
the docs CI gate before merge.
