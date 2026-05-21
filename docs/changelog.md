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

### 6.0.24.* and earlier — see the release timeline

For per-sub-version history of the 6.0.24.* (Aug 2023 — Aug 2025)
and 6.0.23.* (Sep 2022 — Aug 2023) series, see the [Tagged release
timeline](#tagged-release-timeline) below — each tag is a real
release point John shipped, with a bounded diff for the curious.

[John's NodeChangeLog][nodechangelog] groups changes by major
version line (6.0.24.1, 6.0.25.1) but tracks individual
sub-versions in parenthesised notation; the timeline below
cross-references those sub-versions to commit SHAs so you can
drill into any specific one.

## Tagged release timeline

Every upstream-tagged release point in the GitHub mirror,
oldest first.  ``Date`` is the tagger date (when John pushed
the tag — his release date).  ``Versions.h`` is the
``KVerstring`` value at the tagged commit, i.e. what the
binary's ``-v`` output reports — note that the *tag name* and
the *Versions.h value* drift by 1-5 sub-versions because John
tags forward of his commit-time version stamp.

Hotfix-suffix tags (``a``, ``b``, ``c``, ``.1``) are
same-``Versions.h`` follow-up release iterations.

### 6.0.23.* — 2022-09-07 to 2023-08-12 (28 tagged releases)

| Date | Tag | Versions.h | Commit |
|---|---|---|---|
| 2022-09-07 | `6.0.23.18` | `6.0.23.18` | [`e3ea58d`](https://github.com/g8bpq/linbpq/commit/e3ea58d) |
| 2022-09-22 | `6.0.23.20` | `6.0.23.18` | [`9d98903`](https://github.com/g8bpq/linbpq/commit/9d98903) |
| 2022-10-03 | `6.0.23.21` | `6.0.23.18` | [`9d98903`](https://github.com/g8bpq/linbpq/commit/9d98903) |
| 2022-10-18 | `6.0.23.22` | `6.0.23.21` | [`4a4271c`](https://github.com/g8bpq/linbpq/commit/4a4271c) |
| 2022-10-23 | `6.0.23.24` | `6.0.23.22` | [`2bd6071`](https://github.com/g8bpq/linbpq/commit/2bd6071) |
| 2022-11-12 | `6.0.23.25` | `6.0.23.24` | [`9b5f7cc`](https://github.com/g8bpq/linbpq/commit/9b5f7cc) |
| 2022-11-14 | `6.0.23.26` | `6.0.23.25` | [`e3db09d`](https://github.com/g8bpq/linbpq/commit/e3db09d) |
| 2022-11-18 | `6.0.23.27` | `6.0.23.27` | [`6c6848b`](https://github.com/g8bpq/linbpq/commit/6c6848b) |
| 2022-11-23 | `6.0.23.29` | `6.0.23.27` | [`6c6848b`](https://github.com/g8bpq/linbpq/commit/6c6848b) |
| 2022-11-23 | `6.0.23.30` | `6.0.23.29` | [`be0f2b8`](https://github.com/g8bpq/linbpq/commit/be0f2b8) |
| 2022-12-09 | `6.0.23.33` | `6.0.23.30` | [`e95c1f3`](https://github.com/g8bpq/linbpq/commit/e95c1f3) |
| 2022-12-31 | `6.0.23.34` | `6.0.23.33` | [`ebc845e`](https://github.com/g8bpq/linbpq/commit/ebc845e) |
| 2023-01-06 | `6.0.23.36` | `6.0.23.34` | [`90bdcbe`](https://github.com/g8bpq/linbpq/commit/90bdcbe) |
| 2023-01-25 | `6.0.23.42` | `6.0.23.36` | [`9a44d00`](https://github.com/g8bpq/linbpq/commit/9a44d00) |
| 2023-02-05 | `6.0.23.46` | `6.0.23.42` | [`c15de2c`](https://github.com/g8bpq/linbpq/commit/c15de2c) |
| 2023-03-02 | `6.0.23.51` | `6.0.23.46` | [`c32ef4e`](https://github.com/g8bpq/linbpq/commit/c32ef4e) |
| 2023-03-16 | `6.0.23.55` | `6.0.23.51` | [`39da8ff`](https://github.com/g8bpq/linbpq/commit/39da8ff) |
| 2023-03-18 | `6.0.23.56` | `6.0.23.55` | [`a792602`](https://github.com/g8bpq/linbpq/commit/a792602) |
| 2023-04-03 | `6.0.23.58` | `6.0.23.56` | [`814c68f`](https://github.com/g8bpq/linbpq/commit/814c68f) |
| 2023-04-06 | `6.0.23.59` | `6.0.23.58` | [`f1bf68a`](https://github.com/g8bpq/linbpq/commit/f1bf68a) |
| 2023-05-16 | `6.0.23.66` | `6.0.23.59` | [`60ff21f`](https://github.com/g8bpq/linbpq/commit/60ff21f) |
| 2023-05-25 | `6.0.23.70` | `6.0.23.66` | [`ac7e6b9`](https://github.com/g8bpq/linbpq/commit/ac7e6b9) |
| 2023-05-26 | `6.0.23.71` | `6.0.23.70` | [`4924c12`](https://github.com/g8bpq/linbpq/commit/4924c12) |
| 2023-06-21 | `6.0.23.76` | `6.0.23.71` | [`a21121f`](https://github.com/g8bpq/linbpq/commit/a21121f) |
| 2023-06-29 | `6.0.23.77` | `6.0.23.76` | [`75b5bcc`](https://github.com/g8bpq/linbpq/commit/75b5bcc) |
| 2023-07-29 | `6.0.23.81` | `6.0.23.77` | [`ed81fc5`](https://github.com/g8bpq/linbpq/commit/ed81fc5) |
| 2023-08-06 | `6.0.23.82` | `6.0.23.81` | [`b77dbd8`](https://github.com/g8bpq/linbpq/commit/b77dbd8) |
| 2023-08-12 | `6.0.24.1` | `6.0.23.82` | [`55dc284`](https://github.com/g8bpq/linbpq/commit/55dc284) |

### 6.0.24.* — 2023-08-14 to 2025-08-23 (68 tagged releases)

| Date | Tag | Versions.h | Commit |
|---|---|---|---|
| 2023-08-14 | `6.0.24.2` | `6.0.24.1` | [`0bdcbb4`](https://github.com/g8bpq/linbpq/commit/0bdcbb4) |
| 2023-09-02 | `6.0.24.6` | `6.0.24.2` | [`084ecb7`](https://github.com/g8bpq/linbpq/commit/084ecb7) |
| 2023-09-10 | `6.0.24.8` | `6.0.24.6` | [`34b5c72`](https://github.com/g8bpq/linbpq/commit/34b5c72) |
| 2023-09-14 | `6.0.24.10` | `6.0.24.9` | [`84b3067`](https://github.com/g8bpq/linbpq/commit/84b3067) |
| 2023-09-14 | `6.0.24.9` | `6.0.24.8` | [`fdc47ca`](https://github.com/g8bpq/linbpq/commit/fdc47ca) |
| 2023-10-08 | `6.0.24.13` | `6.0.24.11` | [`27fd28f`](https://github.com/g8bpq/linbpq/commit/27fd28f) |
| 2023-10-08 | `6.0.24.14` | `6.0.24.13` | [`318dbc5`](https://github.com/g8bpq/linbpq/commit/318dbc5) |
| 2023-10-09 | `6.0.24.15` | `6.0.24.14` | [`b4f82c7`](https://github.com/g8bpq/linbpq/commit/b4f82c7) |
| 2023-10-26 | `6.0.24.16` | `6.0.24.15` | [`84cbedb`](https://github.com/g8bpq/linbpq/commit/84cbedb) |
| 2023-11-06 | `6.0.24.18` | `6.0.24.16` | [`7710398`](https://github.com/g8bpq/linbpq/commit/7710398) |
| 2023-11-15 | `6.0.24.20` | `6.0.24.18` | [`66a5f51`](https://github.com/g8bpq/linbpq/commit/66a5f51) |
| 2023-11-23 | `6.0.24.21` | `6.0.24.20` | [`e134427`](https://github.com/g8bpq/linbpq/commit/e134427) |
| 2023-12-03 | `6.0.24.22` | `6.0.24.21` | [`35db10e`](https://github.com/g8bpq/linbpq/commit/35db10e) |
| 2023-12-11 | `6.0.24.24` | `6.0.24.22` | [`bdb1f12`](https://github.com/g8bpq/linbpq/commit/bdb1f12) |
| 2023-12-13 | `6.0.24.24a` | `6.0.24.24` | [`e147a79`](https://github.com/g8bpq/linbpq/commit/e147a79) |
| 2023-12-17 | `6.0.24.25` | `6.0.24.24` | [`ee5bce0`](https://github.com/g8bpq/linbpq/commit/ee5bce0) |
| 2024-01-08 | `6.0.24.26` | `6.0.24.25` | [`e02ff3e`](https://github.com/g8bpq/linbpq/commit/e02ff3e) |
| 2024-01-15 | `6.0.24.27` | `6.0.24.26` | [`74433f7`](https://github.com/g8bpq/linbpq/commit/74433f7) |
| 2024-02-11 | `6.0.24.29` | `6.0.24.27` | [`0b2206c`](https://github.com/g8bpq/linbpq/commit/0b2206c) |
| 2024-02-21 | `6.0.24.30` | `6.0.24.29` | [`eb4ab64`](https://github.com/g8bpq/linbpq/commit/eb4ab64) |
| 2024-03-21 | `6.0.24.33` | `6.0.24.30` | [`cbb7a5c`](https://github.com/g8bpq/linbpq/commit/cbb7a5c) |
| 2024-04-05 | `6.0.24.34` | `6.0.24.33` | [`64a95ea`](https://github.com/g8bpq/linbpq/commit/64a95ea) |
| 2024-04-24 | `6.0.24.36` | `6.0.24.34` | [`f1fe8e6`](https://github.com/g8bpq/linbpq/commit/f1fe8e6) |
| 2024-05-27 | `6.0.24.38` | `6.0.24.36` | [`2bb96a9`](https://github.com/g8bpq/linbpq/commit/2bb96a9) |
| 2024-06-28 | `6.0.24.40` | `6.0.24.38` | [`26c4358`](https://github.com/g8bpq/linbpq/commit/26c4358) |
| 2024-08-27 | `6.0.24.42` | `6.0.24.40` | [`f5a7672`](https://github.com/g8bpq/linbpq/commit/f5a7672) |
| 2024-10-06 | `6.0.24.45` | `6.0.24.42` | [`48544f8`](https://github.com/g8bpq/linbpq/commit/48544f8) |
| 2024-10-18 | `6.0.24.46` | `6.0.24.45` | [`703ecaf`](https://github.com/g8bpq/linbpq/commit/703ecaf) |
| 2024-10-19 | `6.0.24.47` | `6.0.24.46` | [`fdfd727`](https://github.com/g8bpq/linbpq/commit/fdfd727) |
| 2024-10-26 | `6.0.24.48` | `6.0.24.47` | [`033b8fb`](https://github.com/g8bpq/linbpq/commit/033b8fb) |
| 2024-10-27 | `6.0.24.48a` | `6.0.24.48` | [`0a458ce`](https://github.com/g8bpq/linbpq/commit/0a458ce) |
| 2024-10-27 | `6.0.24.48b` | `6.0.24.48` | [`3b6091e`](https://github.com/g8bpq/linbpq/commit/3b6091e) |
| 2024-10-28 | `6.0.24.48c` | `6.0.24.48` | [`c3746d1`](https://github.com/g8bpq/linbpq/commit/c3746d1) |
| 2024-10-30 | `6.0.24.48d` | `6.0.24.48` | [`d642ff5`](https://github.com/g8bpq/linbpq/commit/d642ff5) |
| 2024-10-31 | `6.0.24.48e` | `6.0.24.48` | [`6472165`](https://github.com/g8bpq/linbpq/commit/6472165) |
| 2024-11-04 | `6.0.24.49` | `6.0.24.48` | [`4745452`](https://github.com/g8bpq/linbpq/commit/4745452) |
| 2024-11-10 | `6.0.24.50` | `6.0.24.49` | [`46adaea`](https://github.com/g8bpq/linbpq/commit/46adaea) |
| 2024-11-28 | `6.0.24.51` | `6.0.24.50` | [`f2ca803`](https://github.com/g8bpq/linbpq/commit/f2ca803) |
| 2024-11-29 | `6.0.24.51a` | `6.0.24.51` | [`ba4a34b`](https://github.com/g8bpq/linbpq/commit/ba4a34b) |
| 2024-11-30 | `6.0.24.52` | `6.0.24.51` | [`743e2d8`](https://github.com/g8bpq/linbpq/commit/743e2d8) |
| 2024-12-02 | `6.0.24.53` | `6.0.24.52` | [`7e50913`](https://github.com/g8bpq/linbpq/commit/7e50913) |
| 2024-12-14 | `6.0.24.54` | `6.0.24.53` | [`982e2e5`](https://github.com/g8bpq/linbpq/commit/982e2e5) |
| 2025-01-05 | `6.0.24.55` | `6.0.24.54` | [`f7eef80`](https://github.com/g8bpq/linbpq/commit/f7eef80) |
| 2025-01-06 | `6.0.24.56` | `6.0.24.55` | [`6fda6fd`](https://github.com/g8bpq/linbpq/commit/6fda6fd) |
| 2025-02-02 | `6.0.24.59` | `6.0.24.56` | [`d42eee0`](https://github.com/g8bpq/linbpq/commit/d42eee0) |
| 2025-02-02 | `6.0.24.59a` | `6.0.24.59` | [`f9898cf`](https://github.com/g8bpq/linbpq/commit/f9898cf) |
| 2025-02-02 | `6.0.24.59c` | `6.0.24.59` | [`488630c`](https://github.com/g8bpq/linbpq/commit/488630c) |
| 2025-02-11 | `6.0.24.61` | `6.0.24.59` | [`488630c`](https://github.com/g8bpq/linbpq/commit/488630c) |
| 2025-02-15 | `6.0.24.62` | `6.0.24.61` | [`d5c89ec`](https://github.com/g8bpq/linbpq/commit/d5c89ec) |
| 2025-02-20 | `6.0.24.64` | `6.0.24.62` | [`83bc496`](https://github.com/g8bpq/linbpq/commit/83bc496) |
| 2025-02-21 | `6.0.24.65` | `6.0.24.64` | [`098dc64`](https://github.com/g8bpq/linbpq/commit/098dc64) |
| 2025-03-03 | `6.0.24.66` | `6.0.24.65` | [`d3c2c5d`](https://github.com/g8bpq/linbpq/commit/d3c2c5d) |
| 2025-03-13 | `6.0.24.67` | `6.0.24.66` | [`f9a9cb1`](https://github.com/g8bpq/linbpq/commit/f9a9cb1) |
| 2025-03-28 | `6.0.24.69` | `6.0.24.67` | [`eee55a9`](https://github.com/g8bpq/linbpq/commit/eee55a9) |
| 2025-03-31 | `6.0.24.69.1` | `6.0.24.69` | [`7ed5345`](https://github.com/g8bpq/linbpq/commit/7ed5345) |
| 2025-04-17 | `6.0.24.70` | `6.0.24.69` | [`5da7d4d`](https://github.com/g8bpq/linbpq/commit/5da7d4d) |
| 2025-05-16 | `6.0.24.71` | `6.0.24.70` | [`4a7536c`](https://github.com/g8bpq/linbpq/commit/4a7536c) |
| 2025-06-02 | `6.0.24.72` | `6.0.24.71` | [`2af4cf3`](https://github.com/g8bpq/linbpq/commit/2af4cf3) |
| 2025-06-05 | `6.0.24.72a` | `6.0.24.72` | [`fcb3973`](https://github.com/g8bpq/linbpq/commit/fcb3973) |
| 2025-06-09 | `6.0.24.73` | `6.0.24.73` | [`6620d4a`](https://github.com/g8bpq/linbpq/commit/6620d4a) |
| 2025-06-09 | `6.0.24.74` | `6.0.24.73` | [`7f1f96e`](https://github.com/g8bpq/linbpq/commit/7f1f96e) |
| 2025-06-26 | `6.0.24.75` | `6.0.24.74` | [`0583ca8`](https://github.com/g8bpq/linbpq/commit/0583ca8) |
| 2025-07-18 | `6.0.24.76` | `6.0.24.75` | [`48f7c61`](https://github.com/g8bpq/linbpq/commit/48f7c61) |
| 2025-07-22 | `6.0.24.77` | `6.0.24.76` | [`3143e32`](https://github.com/g8bpq/linbpq/commit/3143e32) |
| 2025-07-30 | `6.0.24.78` | `6.0.24.77` | [`3103c10`](https://github.com/g8bpq/linbpq/commit/3103c10) |
| 2025-08-06 | `6.0.24.80` | `6.0.24.78` | [`1571be3`](https://github.com/g8bpq/linbpq/commit/1571be3) |
| 2025-08-17 | `6.0.24.82` | `6.0.24.80` | [`cbc7974`](https://github.com/g8bpq/linbpq/commit/cbc7974) |
| 2025-08-23 | `6.0.25.1` | `6.0.24.82` | [`201bc42`](https://github.com/g8bpq/linbpq/commit/201bc42) |

### 6.0.25.* — 2025-10-10 to 2026-05-17 (8 tagged releases)

| Date | Tag | Versions.h | Commit |
|---|---|---|---|
| 2025-10-10 | `6.0.25.6` | `6.0.25.1` | [`1e51a39`](https://github.com/g8bpq/linbpq/commit/1e51a39) |
| 2025-10-22 | `6.0.25.8` | `6.0.25.6` | [`44916f4`](https://github.com/g8bpq/linbpq/commit/44916f4) |
| 2025-10-28 | `6.0.25.9` | `6.0.25.8` | [`c3e618e`](https://github.com/g8bpq/linbpq/commit/c3e618e) |
| 2025-11-10 | `6.0.25.11` | `6.0.25.9` | [`8e5adbc`](https://github.com/g8bpq/linbpq/commit/8e5adbc) |
| 2025-11-16 | `6.0.25.12` | `6.0.25.11` | [`8e3a121`](https://github.com/g8bpq/linbpq/commit/8e3a121) |
| 2025-11-26 | `6.0.25.13` | `6.0.25.12` | [`513d551`](https://github.com/g8bpq/linbpq/commit/513d551) |
| 2025-12-26 | `6.0.25.15` | `6.0.25.13` | [`f539768`](https://github.com/g8bpq/linbpq/commit/f539768) |
| 2026-05-17 | `6.0.25.28` | `6.0.25.23` | [`225fbb1`](https://github.com/g8bpq/linbpq/commit/225fbb1) |

