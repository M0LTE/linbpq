# Release notes

Per-release notes for the M0LTE fork.  The release cadence
tracks [`g8bpq/linbpq`][upstream] — each upstream release we
sync to becomes a versioned snapshot in this site, with an entry
below describing what changed in the binary and what changed
fork-side.

For canonical, exhaustive upstream history see G8BPQ's
[BPQ32 Node Changelog][nodechangelog] and
[Support Programs Changelog][supportprogs].

[upstream]: https://github.com/g8bpq/linbpq
[nodechangelog]: https://www.cantab.net/users/john.wiseman/Documents/NodeChangeLog.html
[supportprogs]: https://www.cantab.net/users/john.wiseman/Documents/SupportProgsChangeLog.html

## 6.0.25.28 — 17 May 2026

Upstream sync to [g8bpq/linbpq `d84bcda`][6.0.25.28].

### Behaviour changes from upstream

- **AGW**: digipeater paths longer than 7 hops are now rejected
  with a clean disconnect (`AGWAPI.c::ProcessAGWCommand`).
- **BBS forwarding**: `AllowBlocked` and `AllowCompressed`
  partner-config keywords now move together — setting either
  forces the other on.  Inbound forwarding sessions advertising
  the FBB `F` flag without compression are hard-disconnected
  rather than silently downgraded to MBL
  (`BBSUtilities.c::Parse_SID`, `SetupForwardingStruct`).
  See the
  [inter-BBS forwarding page](subsystems/bbs-forwarding.md#fbb-protocol-toggles)
  for the new behaviour.
- **BBS PG commands**: the `PG <server> [args]` command string is
  now validated to be alphanumeric + spaces only before being
  passed to the shell (`BBSUtilities.c::run_pg`).
- **NET/ROM**: hardened route-structure handling in `BPQINP3.c`.
- Buffer-size bumps and housekeeping across `Cmd.c`,
  `CommonCode.c`, `HTTPcode.c`, `LinBPQ.c` — no externally
  visible behaviour change.

### Fork-side changes shipped alongside

- **HTML-from-C extraction backed out.**  Earlier fork work
  extracted the inlined HTML templates from `WebMail.c`,
  `BBSHTMLConfig.c`, `APRSCode.c`, `HTTPcode.c` and
  `templatedefs.c` into standalone `HTML/*.txt` files.  Since
  this work hadn't been upstreamed to John, every upstream
  release was producing large conflicts in those files for no
  benefit.  Reverted on this release; recoverable from the
  `archive/html-extraction` branch.
- **Versioned documentation via [mike].**  The site now ships
  one snapshot per upstream release; the version switcher in
  the page header lets you pin to a specific BPQ version.  This
  release is the first to be versioned; older content is
  backfilled at `/6.0.25.23/`.
- **Docker image tag scheme.**  Image tags now mirror the
  upstream BPQ version: `m0lte/linbpq:6.0.25.28` for this
  release, plus `:latest` always pointing at the newest
  release.  Master-branch builds publish as
  `m0lte/linbpq:master-<sha>`; `:latest` is no longer moved by
  master pushes.
- **CI runner moved to self-hosted.**  No external behaviour
  change — but fork contributors should note that PR validation
  now depends on the M0LTE-hosted runner being available.

[6.0.25.28]: https://github.com/g8bpq/linbpq/commit/d84bcda
[mike]: https://github.com/jimporter/mike

### Upgrading

- **Docker:** `docker pull m0lte/linbpq:latest` (resolves to
  6.0.25.28), or pin with `m0lte/linbpq:6.0.25.28`.
- **Build from source:** standard `make` against this release.
- **BBS sysops:** re-check the FwdDetail screen for each
  forwarding partner — if you'd set `AllowBlocked=1` and
  `AllowCompressed=0` (or vice versa), 6.0.25.28 now treats that
  config as if both were `=1`.  Any partner whose SID came back
  blocked-without-compression will now be hard-disconnected
  rather than silently downgraded; the partner's side of the
  config needs aligning.

## 6.0.25.23 — 4 March 2026

Baseline for the M0LTE fork's published-tag tracking.  Upstream
release at [g8bpq/linbpq `225fbb1`][6.0.25.23].

[6.0.25.23]: https://github.com/g8bpq/linbpq/commit/225fbb1

---

## Upstream releases before the M0LTE fork's tracking

The entries below cover upstream releases that ship in the
binary the M0LTE fork inherited from but that predate this site's
versioned-docs era.  They're backfilled from independent
analysis of each upstream commit's diff against
[g8bpq/linbpq][upstream], then cross-validated against John's
[NodeChangeLog][nodechangelog] where it has overlapping coverage
— the changelog stops at 6.0.25.1 (Aug 2025), so the 6.0.25.6 →
6.0.25.22 entries below are diff-derived only.

Each version row labels the entry with `(diff-only)` if there's
no upstream changelog text to compare against, or `(cross-checked)`
if John's notes mention the same area.  Discrepancies are called
out inline.

### 6.0.25.22 — 2 March 2026 (diff-only)

Upstream commit [`34f44ed`][6.0.25.22].  Wide cleanup pass.

- `BPQINP3.c` (~300 lines): more INP3 routing churn — the L3RTT
  message-handling rework that ran through the .6–.15 stretch
  appears to settle here.
- `BBSUtilities.c` (~70 lines): BBS-side validation tweaks
  ahead of the 6.0.25.28 PG / blocked-uncompressed work.
- `BPQMail.rc` (~1090 lines): Windows BPQMail resource (dialog)
  layout rebuild.  No Linux impact.
- `AGWAPI.c` (~24 lines): minor AGW-server housekeeping.

[6.0.25.22]: https://github.com/g8bpq/linbpq/commit/34f44ed

### 6.0.25.15 — 26 December 2025 (diff-only)

Upstream commit [`b90e6bd`][6.0.25.15].  Christmas INP3 push.

- `BPQINP3.c` (~340 lines, the biggest single-release change in
  the 25.* series): another round of routing-table accounting
  refinements.
- `BBSHTMLConfig.c`, `BBSUtilities.c`, `BPQMailConfig.c`: minor
  BBS surface touches.
- `Cmd.c` (~40 lines): node-prompt command edge-case fixes.

[6.0.25.15]: https://github.com/g8bpq/linbpq/commit/b90e6bd

### 6.0.25.13 — 26 November 2025 (diff-only)

Upstream commit [`f539768`][6.0.25.13].  Notable for being one of
the few releases that *deletes* code on net — `APRSCode.c`
shrinks by ~106 lines while `BPQINP3.c` continues evolving
(~250 lines).  `Bpq32.c` and `HTTPcode.c` touched lightly.

[6.0.25.13]: https://github.com/g8bpq/linbpq/commit/f539768

### 6.0.25.12 — 16 November 2025 (diff-only)

Upstream commit [`513d551`][6.0.25.12].  Mainly node-prompt
commands and NET/ROM:

- `Cmd.c` (~180 lines): command-table additions / refinements.
- `BPQINP3.c` (~85 lines): same routing rework.
- `L4Code.c`, `NETROMTCP.c`: minor transport-layer tweaks.

[6.0.25.12]: https://github.com/g8bpq/linbpq/commit/513d551

### 6.0.25.11 — 10 November 2025 (diff-only)

Upstream commit [`8e3a121`][6.0.25.11].  Events / chat-node
surface:

- `Events.c` (~155 lines), `cMain.c` (~65 lines).
- `L4Code.c`, `NETROMTCP.c`: NET/ROM-over-TCP carry-over from
  6.0.25.9.

[6.0.25.11]: https://github.com/g8bpq/linbpq/commit/8e3a121

### 6.0.25.9 — 28 October 2025 (diff-only)

Upstream commit [`8e5adbc`][6.0.25.9].  ARDOP-centric.

- `ARDOP.c` (~155 lines): session-management rework.
- `Events.c` (~145 lines), `Bpq32.c` (~95 lines): event handling.
- Small `APRSCode.c`, `BBSUtilities.c`, `DRATS.c` touches.

[6.0.25.9]: https://github.com/g8bpq/linbpq/commit/8e5adbc

### 6.0.25.8 — 22 October 2025 (diff-only)

Upstream commit [`c3e618e`][6.0.25.8].  The biggest single
release in the gap range — ~2500 line insertions across 33
files.

- **New `NETROMTCP.c`** (~550 lines): NET/ROM over TCP transport.
- `Events.c` rewrite (~930 lines): the biggest single-file
  change in the 25.* series.
- `Cmd.c` (~270 lines), `L4Code.c` (~420 lines): NET/ROM L4 and
  command-table rework, paired with the new transport.
- `TelnetV6.c` (~115 lines), `config.c` (~185 lines): connection
  and parser surface touched alongside.

[6.0.25.8]: https://github.com/g8bpq/linbpq/commit/c3e618e

### 6.0.25.6 — 10 October 2025 (diff-only)

Upstream commit [`44916f4`][6.0.25.6].  The first release after
6.0.25.1; mostly INP3 protocol-version work plus a NodeAPI
expansion.

- `BPQINP3.c` (~325 lines): the L3RTT-message FLAGS field grows
  from 10 to 20 bytes and gains a `$H<MaxHops>` flag advertising
  the local node's hop limit; the software-version stamp in the
  RTT broadcast bumps `BPQ32001` → `BPQ32002`.  Debug logging
  gated behind a runtime `DEBUGINP3` flag (less console noise on
  busy nodes).  Verified against the diff at `BPQINP3.c`
  init/teardown.
- `nodeapi.c` (~200 lines): more JSON API endpoints.
- `L2Code.c` (~205 lines), `Cmd.c` (~140 lines), `Moncode.c`
  (~90 lines): AX.25 link and monitor surface widened.

[6.0.25.6]: https://github.com/g8bpq/linbpq/commit/44916f4

### 6.0.25.1 — 27 August 2025 (cross-checked against NodeChangeLog)

Upstream commit [`1e51a39`][6.0.25.1].  The 6.0.25 series
release-marker.

**Diff-derived view** (what I see in 6.0.24.82 → 6.0.25.1):
the commit itself is small — about 12 files, 300 line insertions
— dominated by a new `ScanHID.c` / `ScanHID.vcproj` pair (a
Windows USB-HID device scanner, presumably backing the rigcontrol
SDRAngel and FTDX10 work John mentions) and small `RigControl.c`,
`BBSUtilities.c`, `L3Code.c` updates.

The commit is NOT a full picture of what shipped between
6.0.24.1 and 6.0.25.1 — upstream's sub-version cadence is
finer-grained than the commits in the GitHub mirror, and
6.0.25.1 represents the end of a long sub-version stream.

**Cross-check against [upstream NodeChangeLog][nodechangelog]:**
John's 6.0.25.1 entry lists ~80 sub-version bullets covering the
year's work.  Major themes that align with what we'd derive from
the wider diff include:

- AX.25 / NET/ROM transport: L4 frame ordering, INP3 routing,
  KISS interlocks, NETROM compression, NET/ROM-over-TCP
  groundwork.
- New rigcontrol drivers (SDRAngel, FTDX10) and improvements
  across existing ones (FLRIG, ICF8101 mode setting, KAM, ARDOP).
- BBS / mail / WebMail: autorefresh fixes, MailAPI tweaks,
  potential-overflow guards.
- Telnet path hardening (security-flavoured: buffer-overflow
  fixes, `SECURETELNET` default changed to 1).
- MQTT interface introduction.
- M0LTE Map (this fork's monitoring endpoint) reporting moved
  to a separate thread for responsiveness.
- Stack backtrace on `SIGSEGV` / `SIGABRT` on Linux (new
  diagnostic).
- Save MH and NODES every hour (durability).

No material disagreement between the diff view and John's
notes; the cross-check confirms the diff is just the surface
of a release that accreted ~80 sub-version commits' worth of
work in the upstream working tree.

[6.0.25.1]: https://github.com/g8bpq/linbpq/commit/1e51a39

### 6.0.24.* and earlier — cross-validated only

For the 6.0.24.* (Aug 2023 — Aug 2025) and 6.0.23.* (Jun 2022 —
Aug 2023) series, the per-major-version diffs are too large to
analyse meaningfully from this fork's perspective — each "major"
release spans about a year of fine-grained upstream development
that gets condensed into a single GitHub commit.  Rather than
fabricate diff-level detail at that scale, defer to upstream:

- [`6.0.24.1`][6.0.24.1] (10 Aug 2023): NODES wildcard
  improvements, VARA driver lifecycle commands, RADIO PTT test
  command, FLDIGI driver improvements, web-socket WebMail
  autorefresh, GPSD support, FreeBSD compatibility additions,
  FreeData driver groundwork.  See
  [upstream changelog][nodechangelog].
- 6.0.23.* series (Jun 2022 — Aug 2023): the GitHub mirror's
  oldest 6.0.23 commit is [`6.0.23.21`][6.0.23.21]; earlier
  sub-versions exist only as upstream sub-version stamps.  The
  series introduced RTL-SDR rigcontrol, RMS Relay SYNC,
  AIS/ADSB support, FLRIG backend, DRATS interface basics, and
  the FreeData modem driver.  See
  [upstream changelog][nodechangelog].

For versions older than 6.0.23, [John's NodeChangeLog][nodechangelog]
is the authoritative source going back to 2010.

[6.0.24.1]: https://github.com/g8bpq/linbpq/commit/0bdcbb4
[6.0.23.21]: https://github.com/g8bpq/linbpq/commit/4a4271c
