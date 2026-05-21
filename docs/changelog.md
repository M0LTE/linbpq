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

## Upstream release history

Each section below covers one upstream-tagged release point,
newest first.  ``Date`` is the tag-push date (when John shipped
the release).  ``Versions.h`` is the ``KVerstring`` value at
that snapshot — note the tag-vs-``Versions.h`` drift is John's
tagging convention; the binary's ``-v`` output reports the
``Versions.h`` value.  Hotfix-suffix tags (``a``, ``b``, ``c``,
``.1``) are same-``Versions.h`` follow-up releases.

Where [John's NodeChangeLog][nodechangelog] has a matching
section — broadly the `.1` markers at major-line boundaries —
the relevant bullets are folded in beneath that release's
heading.  Interim sub-versions get a one-line tag / commit
reference; for per-sub-version detail ``git show <tag>`` against
the upstream repo.

### 6.0.25.15 — 2025-12-26

Tag [`6.0.25.15`](https://github.com/g8bpq/linbpq/commit/f539768); `Versions.h` reports `6.0.25.13`.

Notable for being one of the few releases that *deletes* code
on net — `APRSCode.c` shrinks by ~106 lines while `BPQINP3.c`
continues evolving (~250 lines).  `Bpq32.c` and `HTTPcode.c`
touched lightly.

### 6.0.25.13 — 2025-11-26

Tag [`6.0.25.13`](https://github.com/g8bpq/linbpq/commit/513d551); `Versions.h` reports `6.0.25.12`.

Mainly node-prompt commands and NET/ROM:

- `Cmd.c` (~180 lines): command-table additions / refinements.
- `BPQINP3.c` (~85 lines): same routing rework.
- `L4Code.c`, `NETROMTCP.c`: minor transport-layer tweaks.

### 6.0.25.12 — 2025-11-16

Tag [`6.0.25.12`](https://github.com/g8bpq/linbpq/commit/8e3a121); `Versions.h` reports `6.0.25.11`.

Events / chat-node surface:

- `Events.c` (~155 lines), `cMain.c` (~65 lines).
- `L4Code.c`, `NETROMTCP.c`: NET/ROM-over-TCP carry-over from
  6.0.25.9.

### 6.0.25.11 — 2025-11-10

Tag [`6.0.25.11`](https://github.com/g8bpq/linbpq/commit/8e5adbc); `Versions.h` reports `6.0.25.9`.

ARDOP-centric.

- `ARDOP.c` (~155 lines): session-management rework.
- `Events.c` (~145 lines), `Bpq32.c` (~95 lines): event handling.
- Small `APRSCode.c`, `BBSUtilities.c`, `DRATS.c` touches.

### 6.0.25.9 — 2025-10-28

Tag [`6.0.25.9`](https://github.com/g8bpq/linbpq/commit/c3e618e); `Versions.h` reports `6.0.25.8`.

The biggest single release in the gap range — ~2500 line
insertions across 33 files.

- **New `NETROMTCP.c`** (~550 lines): NET/ROM over TCP transport.
- `Events.c` rewrite (~930 lines): the biggest single-file
  change in the 25.* series.
- `Cmd.c` (~270 lines), `L4Code.c` (~420 lines): NET/ROM L4 and
  command-table rework, paired with the new transport.
- `TelnetV6.c` (~115 lines), `config.c` (~185 lines): connection
  and parser surface touched alongside.

### 6.0.25.8 — 2025-10-22

Tag [`6.0.25.8`](https://github.com/g8bpq/linbpq/commit/44916f4); `Versions.h` reports `6.0.25.6`.

The first release after 6.0.25.1; mostly INP3 protocol-version
work plus a NodeAPI expansion.

- `BPQINP3.c` (~325 lines): the L3RTT-message FLAGS field grows
  from 10 to 20 bytes and gains a `$H<MaxHops>` flag advertising
  the local node's hop limit; the software-version stamp in the
  RTT broadcast bumps `BPQ32001` → `BPQ32002`.  Debug logging
  gated behind a runtime `DEBUGINP3` flag.
- `nodeapi.c` (~200 lines): more JSON API endpoints.
- `L2Code.c` (~205 lines), `Cmd.c` (~140 lines), `Moncode.c`
  (~90 lines): AX.25 link and monitor surface widened.

### 6.0.25.6 — 2025-10-10

Tag [`6.0.25.6`](https://github.com/g8bpq/linbpq/commit/1e51a39); `Versions.h` reports `6.0.25.1`.

### 6.0.25.1 — 2025-08-23

Tag [`6.0.25.1`](https://github.com/g8bpq/linbpq/commit/201bc42); `Versions.h` reports `6.0.24.82`.

Per [John's NodeChangeLog][nodechangelog]:

- Fix 64 bit compatibility problems in SCSTracker and UZ7HO drivers
- Add Chat PACLEN config (5)
- Fix NC to Application Call (6)
- Fix INP3 L3RTT messages on Linux and correct RTT calculation (9)
- Get Beacon config from config file on Windows (9)
- fix processing DED TNC Emulator M command with space between M and params (10)
- Fix sending UI frames on SCSPACTOR (11)
- Dont allow ports that can't set digi'ed bit in callsigns to digipeat. (11)
- Add SDRAngel rig control (11)
- Add option to specify config and data directories on linbpq (12)
- Allow zero resptime (send RR immediately) (13)
- Make sure CMD bit is set on UI frames
- Add setting Modem Flags in QtSM AGW mode
- If FT847 om PTC Port send a "Cat On" command (17)
- Fix some 63 port bugs in RigCOntrol (17)
- Fix 63 port bug in Bridging (18)
- Add FTDX10 Rigcontrol (19)
- Fix 64 bit bug in displaying INP3 Messages (20)
- Improve restart of WinRPR TNC on remote host (21)
- Fix some Rigcontrol issues with empty timebands (22)
- Fix 64 bit bug in processing INP3 Messages (22)
- First pass at api (24)
- Send OK in response to Rigcontrol CMD (24)
- Disable CTS check in WriteComBlock (26)
- Improvments to reporting to M0LTE Map (26)
- IPGateway fix from github user isavitsky (27)
- Fix possible crash in SCSPactor PTCPORT code (29)
- Add NodeAPI call sendLinks and remove get from other calls (32)
- Improve validation of Web Beacon Config (33)
- Support SNMP via host ip stack as well as IPGateway (34)
- Switch APRS Map to OSM tile servers (36)
- Fix potential buffer overflow in Telnet login (36)
- Allow longer serial device names (37)
- Fix ICF8101 Mode setting (37)
- Kill link if we are getting repeated RR(F) after timeout
- (Indicating other station is seeing our RR(P) but not the resent I frame) (40)
- Change default of SECURETELNET to 1 (41)
- Add optional ATTACH time limit for ARDOP (42)
- Fix buffer overflow risk in HTTP Terminal(42)
- Fix KISSHF Interlock (43)
- Support other than channel A on HFKISS (43)
- Support additional port info reporting for M0LTE Map (44)
- Allow interlocking of KISS and Session mode ports (eg ARDOP and VARA) (45)
- Add ARDOP UI Packets to MH (45)
- Add support for Qtsm Mgmt Interface (45)
- NodeAPI improvements (46)
- Add MQTT Interface (46)
- Fix buffer leak in ARDOP code(46)
- Fix possible crash if MQTT not in use (47)
- Add optional ATTACH time limit for VARA (48)
- API format fixes (48)
- AGWAPI Add protection against accidental connects from a non-agw application (50)
- Save MH and NODES every hour (51)
- Fix handling long unix device names (now max 250 bytes) (52)
- Fix error reporting in api update (53)
- Coding changes to remove some compiler warnings (53, 54)
- Add MQTT reporting of Mail Events (54)
- Fix beaconong on KISSHF ports (55)
- Fix MailAPI msgs endpoint
- Attempt to fix NC going to wrong application. (57)
- Improve ARDOP end of session code (58)
- Run M0LTE Map reporting in a separate thread (59/60)
- Add RHP support for WhatsPac (59)
- Add timestamps to LIS monitor (60)
- Fix problem with L4 frames being delivered out of sequence (60)
- Add Compression of Netrom connections (62)
- Improve handling of Locked Routes (62)
- Add L4 RESET (Paula G8PZT's extension to NETROM)
- Fix problem using SENDRAW from BPQMail (63)
- Fix compatibility with latest ardopcf (64)
- Fix bug in RHP socket timeout code (65)
- Fix L4 RTT (66)
- Fix RigConrol with Chanxx but no other settings (66)
- Add option to compress L2 frames (67)
- Sort Routes displays (67)
- Fix Ardop session premature close (70)
- Add timestamps to log entries in Web Driver windows (70)
- Generate stack backtrace if SIGSEGV or SIGABRT occur (Linux) (70)
- Remove some debug logging from L2 code (70)
- Fix compiling LinBPQ with nomqtt option (70)
- Improve handling of binary data in RHP interface (70)
- Fix sending KISS commands to multiport or multidropped TNCs (70)
- Add MHUV and MHLV commands (Verbose listing with timestamps in clock time) (70)
- Improvements to INP3 (71)
- Improvements to KAM driver including support for GTOR connects (71)
- Support IPv6 for Telnet outward connects (72)
- Fix decaying NETROM routes (72)
- Add OnlyVer2point0 config command (72)
- Add option to allow AX/UDP on a network using NAT (72)
- Include AGWAPI fixes from Martin KD6YAM to enable use with Paracon terminal (72)
- Fix 64 bit compatiblility issues with AGWAPI (73)
- Fix KAM Pactor Interlock (73)
- Fix Node map reporting, broken in .73 (74)
- Fixes to build on FreeBSD and NetBSD from jg1uaa (77)
- Fix to L4Compress from Steve G7TAJ (77)
- Fix possible FRMR when RNR is cleared by SREJ (78)
- Fix error in .77 L4Compress fix (mine, not Steve's!) (78)
- Fix possible stuck L2 session when handling SREJ (79)
- Allow sending CTRL/G From console (Windows) (80)
- Fix Webmail autorefresh extra threads problem (websock connection lost handling) (82)
- Fix overwriting application alias (83)

### 6.0.24.82 — 2025-08-17

Tag [`6.0.24.82`](https://github.com/g8bpq/linbpq/commit/cbc7974); `Versions.h` reports `6.0.24.80`.

### 6.0.24.80 — 2025-08-06

Tag [`6.0.24.80`](https://github.com/g8bpq/linbpq/commit/1571be3); `Versions.h` reports `6.0.24.78`.

### 6.0.24.78 — 2025-07-30

Tag [`6.0.24.78`](https://github.com/g8bpq/linbpq/commit/3103c10); `Versions.h` reports `6.0.24.77`.

### 6.0.24.77 — 2025-07-22

Tag [`6.0.24.77`](https://github.com/g8bpq/linbpq/commit/3143e32); `Versions.h` reports `6.0.24.76`.

### 6.0.24.76 — 2025-07-18

Tag [`6.0.24.76`](https://github.com/g8bpq/linbpq/commit/48f7c61); `Versions.h` reports `6.0.24.75`.

### 6.0.24.75 — 2025-06-26

Tag [`6.0.24.75`](https://github.com/g8bpq/linbpq/commit/0583ca8); `Versions.h` reports `6.0.24.74`.

### 6.0.24.74 — 2025-06-09

Tag [`6.0.24.74`](https://github.com/g8bpq/linbpq/commit/7f1f96e); `Versions.h` reports `6.0.24.73`.

### 6.0.24.73 — 2025-06-09

Tag [`6.0.24.73`](https://github.com/g8bpq/linbpq/commit/6620d4a); `Versions.h` reports `6.0.24.73`.

### 6.0.24.72a — 2025-06-05

Tag [`6.0.24.72a`](https://github.com/g8bpq/linbpq/commit/fcb3973); `Versions.h` reports `6.0.24.72`.

### 6.0.24.72 — 2025-06-02

Tag [`6.0.24.72`](https://github.com/g8bpq/linbpq/commit/2af4cf3); `Versions.h` reports `6.0.24.71`.

### 6.0.24.71 — 2025-05-16

Tag [`6.0.24.71`](https://github.com/g8bpq/linbpq/commit/4a7536c); `Versions.h` reports `6.0.24.70`.

### 6.0.24.70 — 2025-04-17

Tag [`6.0.24.70`](https://github.com/g8bpq/linbpq/commit/5da7d4d); `Versions.h` reports `6.0.24.69`.

### 6.0.24.69.1 — 2025-03-31

Tag [`6.0.24.69.1`](https://github.com/g8bpq/linbpq/commit/7ed5345); `Versions.h` reports `6.0.24.69`.

### 6.0.24.69 — 2025-03-28

Tag [`6.0.24.69`](https://github.com/g8bpq/linbpq/commit/eee55a9); `Versions.h` reports `6.0.24.67`.

### 6.0.24.67 — 2025-03-13

Tag [`6.0.24.67`](https://github.com/g8bpq/linbpq/commit/f9a9cb1); `Versions.h` reports `6.0.24.66`.

### 6.0.24.66 — 2025-03-03

Tag [`6.0.24.66`](https://github.com/g8bpq/linbpq/commit/d3c2c5d); `Versions.h` reports `6.0.24.65`.

### 6.0.24.65 — 2025-02-21

Tag [`6.0.24.65`](https://github.com/g8bpq/linbpq/commit/098dc64); `Versions.h` reports `6.0.24.64`.

### 6.0.24.64 — 2025-02-20

Tag [`6.0.24.64`](https://github.com/g8bpq/linbpq/commit/83bc496); `Versions.h` reports `6.0.24.62`.

### 6.0.24.62 — 2025-02-15

Tag [`6.0.24.62`](https://github.com/g8bpq/linbpq/commit/d5c89ec); `Versions.h` reports `6.0.24.61`.

### 6.0.24.61 — 2025-02-11

Tag [`6.0.24.61`](https://github.com/g8bpq/linbpq/commit/488630c); `Versions.h` reports `6.0.24.59`.

### 6.0.24.59c — 2025-02-02

Tag [`6.0.24.59c`](https://github.com/g8bpq/linbpq/commit/488630c); `Versions.h` reports `6.0.24.59`.

### 6.0.24.59a — 2025-02-02

Tag [`6.0.24.59a`](https://github.com/g8bpq/linbpq/commit/f9898cf); `Versions.h` reports `6.0.24.59`.

### 6.0.24.59 — 2025-02-02

Tag [`6.0.24.59`](https://github.com/g8bpq/linbpq/commit/d42eee0); `Versions.h` reports `6.0.24.56`.

### 6.0.24.56 — 2025-01-06

Tag [`6.0.24.56`](https://github.com/g8bpq/linbpq/commit/6fda6fd); `Versions.h` reports `6.0.24.55`.

### 6.0.24.55 — 2025-01-05

Tag [`6.0.24.55`](https://github.com/g8bpq/linbpq/commit/f7eef80); `Versions.h` reports `6.0.24.54`.

### 6.0.24.54 — 2024-12-14

Tag [`6.0.24.54`](https://github.com/g8bpq/linbpq/commit/982e2e5); `Versions.h` reports `6.0.24.53`.

### 6.0.24.53 — 2024-12-02

Tag [`6.0.24.53`](https://github.com/g8bpq/linbpq/commit/7e50913); `Versions.h` reports `6.0.24.52`.

### 6.0.24.52 — 2024-11-30

Tag [`6.0.24.52`](https://github.com/g8bpq/linbpq/commit/743e2d8); `Versions.h` reports `6.0.24.51`.

### 6.0.24.51a — 2024-11-29

Tag [`6.0.24.51a`](https://github.com/g8bpq/linbpq/commit/ba4a34b); `Versions.h` reports `6.0.24.51`.

### 6.0.24.51 — 2024-11-28

Tag [`6.0.24.51`](https://github.com/g8bpq/linbpq/commit/f2ca803); `Versions.h` reports `6.0.24.50`.

### 6.0.24.50 — 2024-11-10

Tag [`6.0.24.50`](https://github.com/g8bpq/linbpq/commit/46adaea); `Versions.h` reports `6.0.24.49`.

### 6.0.24.49 — 2024-11-04

Tag [`6.0.24.49`](https://github.com/g8bpq/linbpq/commit/4745452); `Versions.h` reports `6.0.24.48`.

### 6.0.24.48e — 2024-10-31

Tag [`6.0.24.48e`](https://github.com/g8bpq/linbpq/commit/6472165); `Versions.h` reports `6.0.24.48`.

### 6.0.24.48d — 2024-10-30

Tag [`6.0.24.48d`](https://github.com/g8bpq/linbpq/commit/d642ff5); `Versions.h` reports `6.0.24.48`.

### 6.0.24.48c — 2024-10-28

Tag [`6.0.24.48c`](https://github.com/g8bpq/linbpq/commit/c3746d1); `Versions.h` reports `6.0.24.48`.

### 6.0.24.48b — 2024-10-27

Tag [`6.0.24.48b`](https://github.com/g8bpq/linbpq/commit/3b6091e); `Versions.h` reports `6.0.24.48`.

### 6.0.24.48a — 2024-10-27

Tag [`6.0.24.48a`](https://github.com/g8bpq/linbpq/commit/0a458ce); `Versions.h` reports `6.0.24.48`.

### 6.0.24.48 — 2024-10-26

Tag [`6.0.24.48`](https://github.com/g8bpq/linbpq/commit/033b8fb); `Versions.h` reports `6.0.24.47`.

### 6.0.24.47 — 2024-10-19

Tag [`6.0.24.47`](https://github.com/g8bpq/linbpq/commit/fdfd727); `Versions.h` reports `6.0.24.46`.

### 6.0.24.46 — 2024-10-18

Tag [`6.0.24.46`](https://github.com/g8bpq/linbpq/commit/703ecaf); `Versions.h` reports `6.0.24.45`.

### 6.0.24.45 — 2024-10-06

Tag [`6.0.24.45`](https://github.com/g8bpq/linbpq/commit/48544f8); `Versions.h` reports `6.0.24.42`.

### 6.0.24.42 — 2024-08-27

Tag [`6.0.24.42`](https://github.com/g8bpq/linbpq/commit/f5a7672); `Versions.h` reports `6.0.24.40`.

### 6.0.24.40 — 2024-06-28

Tag [`6.0.24.40`](https://github.com/g8bpq/linbpq/commit/26c4358); `Versions.h` reports `6.0.24.38`.

### 6.0.24.38 — 2024-05-27

Tag [`6.0.24.38`](https://github.com/g8bpq/linbpq/commit/2bb96a9); `Versions.h` reports `6.0.24.36`.

### 6.0.24.36 — 2024-04-24

Tag [`6.0.24.36`](https://github.com/g8bpq/linbpq/commit/f1fe8e6); `Versions.h` reports `6.0.24.34`.

### 6.0.24.34 — 2024-04-05

Tag [`6.0.24.34`](https://github.com/g8bpq/linbpq/commit/64a95ea); `Versions.h` reports `6.0.24.33`.

### 6.0.24.33 — 2024-03-21

Tag [`6.0.24.33`](https://github.com/g8bpq/linbpq/commit/cbb7a5c); `Versions.h` reports `6.0.24.30`.

### 6.0.24.30 — 2024-02-21

Tag [`6.0.24.30`](https://github.com/g8bpq/linbpq/commit/eb4ab64); `Versions.h` reports `6.0.24.29`.

### 6.0.24.29 — 2024-02-11

Tag [`6.0.24.29`](https://github.com/g8bpq/linbpq/commit/0b2206c); `Versions.h` reports `6.0.24.27`.

### 6.0.24.27 — 2024-01-15

Tag [`6.0.24.27`](https://github.com/g8bpq/linbpq/commit/74433f7); `Versions.h` reports `6.0.24.26`.

### 6.0.24.26 — 2024-01-08

Tag [`6.0.24.26`](https://github.com/g8bpq/linbpq/commit/e02ff3e); `Versions.h` reports `6.0.24.25`.

### 6.0.24.25 — 2023-12-17

Tag [`6.0.24.25`](https://github.com/g8bpq/linbpq/commit/ee5bce0); `Versions.h` reports `6.0.24.24`.

### 6.0.24.24a — 2023-12-13

Tag [`6.0.24.24a`](https://github.com/g8bpq/linbpq/commit/e147a79); `Versions.h` reports `6.0.24.24`.

### 6.0.24.24 — 2023-12-11

Tag [`6.0.24.24`](https://github.com/g8bpq/linbpq/commit/bdb1f12); `Versions.h` reports `6.0.24.22`.

### 6.0.24.22 — 2023-12-03

Tag [`6.0.24.22`](https://github.com/g8bpq/linbpq/commit/35db10e); `Versions.h` reports `6.0.24.21`.

### 6.0.24.21 — 2023-11-23

Tag [`6.0.24.21`](https://github.com/g8bpq/linbpq/commit/e134427); `Versions.h` reports `6.0.24.20`.

### 6.0.24.20 — 2023-11-15

Tag [`6.0.24.20`](https://github.com/g8bpq/linbpq/commit/66a5f51); `Versions.h` reports `6.0.24.18`.

### 6.0.24.18 — 2023-11-06

Tag [`6.0.24.18`](https://github.com/g8bpq/linbpq/commit/7710398); `Versions.h` reports `6.0.24.16`.

### 6.0.24.16 — 2023-10-26

Tag [`6.0.24.16`](https://github.com/g8bpq/linbpq/commit/84cbedb); `Versions.h` reports `6.0.24.15`.

### 6.0.24.15 — 2023-10-09

Tag [`6.0.24.15`](https://github.com/g8bpq/linbpq/commit/b4f82c7); `Versions.h` reports `6.0.24.14`.

### 6.0.24.14 — 2023-10-08

Tag [`6.0.24.14`](https://github.com/g8bpq/linbpq/commit/318dbc5); `Versions.h` reports `6.0.24.13`.

### 6.0.24.13 — 2023-10-08

Tag [`6.0.24.13`](https://github.com/g8bpq/linbpq/commit/27fd28f); `Versions.h` reports `6.0.24.11`.

### 6.0.24.9 — 2023-09-14

Tag [`6.0.24.9`](https://github.com/g8bpq/linbpq/commit/fdc47ca); `Versions.h` reports `6.0.24.8`.

### 6.0.24.10 — 2023-09-14

Tag [`6.0.24.10`](https://github.com/g8bpq/linbpq/commit/84b3067); `Versions.h` reports `6.0.24.9`.

### 6.0.24.8 — 2023-09-10

Tag [`6.0.24.8`](https://github.com/g8bpq/linbpq/commit/34b5c72); `Versions.h` reports `6.0.24.6`.

### 6.0.24.6 — 2023-09-02

Tag [`6.0.24.6`](https://github.com/g8bpq/linbpq/commit/084ecb7); `Versions.h` reports `6.0.24.2`.

### 6.0.24.2 — 2023-08-14

Tag [`6.0.24.2`](https://github.com/g8bpq/linbpq/commit/0bdcbb4); `Versions.h` reports `6.0.24.1`.

### 6.0.24.1 — 2023-08-12

Tag [`6.0.24.1`](https://github.com/g8bpq/linbpq/commit/55dc284); `Versions.h` reports `6.0.23.82`.

Per [John's NodeChangeLog][nodechangelog]:

- Apply NODES command wildcard to alias as well a call (2)
- Add STOPPORT/STARTPORT to VARA Driver (2)
- Add bandwidth setting to FLRIG interface. (2)
- Fix N VIA (3)
- Fix NODE ADD and NODE DEL (4)
- Improvements to FLRIG Rigcontrol backend (6, 7)
- Fix UZ7HO Window Title Update
- Reject L2 calls with a blank from call (8)
- Update WinRPR Window header with BPQ Port Description (8)
- Fix error in blank call code (9)
- Change web buttons to white on black when pressed (10)
- Fix Port CTEXT paclen on Tracker and WinRPR drivers (11)
- Add RADIO PTT command for testing PTT (11)
- Fix using APPLCALLs on SCSTracker RP call (12)
- Add Rigcntol Web Page (13)
- Fix scan bandwidth change with ARDOPOFDM (13)
- Fix setting Min Pactor Level in SCSPactor (13)
- Fix length of commands sent via CMD_TO_APPL flag (14)
- Add filter by quality option to N display (15)
- Fix VARA Mode reporting to WL2K (16)
- Add FLRIG POWER and TUNE commands (18)
- Fix crash when processing "C " without a call in UZ7HO, FLDIGI or MULTIPSK drivers (19)
- FLDIGI improvements (19)
- Fix hang at start if Telnet port Number > Number of Telnet Streams (20)
- Fix processing C command if first port driver is SCSPACTROR (20)
- Fix crash in UZ7HO driver if bad raw frame received (21)
- Fix using FLARQ chat mode with FLDIGI ddriover (22)
- Fix to KISSHF driver (23)
- Fix for application buffer loss (24)
- Add Web Sockets auto-refresh option for Webmail index page (25)
- Fix FREEDATA driver for compatibility with FreeData TNC version 0.6.4-alpha.3 (25)
- Add SmartID for bridged frames - Send ID only if packets sent recently (26)
- Add option to save and restore received APRS messages (27)
- Add mechanism to run a user program on certain events (27)
- If BeacontoIS is zero don't Gate any of our messages received locally to APRS-IS (28)
- Add Node Help command (28)
- Add APRS Igate RXOnly option (29)
- Fix RMC message handling with prefixes other than GP (29)
- Add GPSD support for APRS (30)
- Attempt to fix Tracker/WinRPR reconnect code (30)
- Changes to FreeDATA - Don't use deamon and add txlevel and send text commands (31)
- Fix interactive commands in tracker driver (33) // Fix SESSIONTIMELIMIT processing
- Add STOPPORT/STARTPORT for UZ7HO driver
- Fix processing of extended QtSM 'g' frame (36)
- Allow setting just freq on Yaseu rigs (37)
- Enable KISSHF driver on Linux (40)
- Allow AISHOST and ADSBHOST to be a name as well as an address (41)
- Fix Interlock of incoming UZ7HO connections (41)
- Disable VARA Actions menu if not sysop (41)
- Fix Port CTEXT on UZ7HO B C or D channels (42)
- Fix repeated trigger of SessionTimeLimit (43) // Fix posible memory corruption in UpateMH (44)
- Add PHG to APRS beacons (45)
- Dont send DM to stations in exclude list(45)
- Improvements to RMS Relay SYNC Mode (46)
- Check L4 connects against EXCLUDE list (47)
- Add vaidation of LOC in WL2K Session Reports (49)
- Change gpsd support for compatibility with Share Gps (50)
- Switch APRS Map to my Tiles (52)
- Fix using ; in UNPROTO Mode messages (52)
- Use sha1 code from https://www.packetizer.com/security/sha1/ instead of openssl (53)
- Fix TNC Emulator Monitoring (53)
- Fix attach and connect on Telnet port bug introduced in .55 (56)
- Fix stopping WinRPR TNC and Start/Stop UZ7HO TNCX on Linux (57)
- Fix stack size in beginthread for MAC (58)
- Add NETROM over VARA (60)
- Add Disconnect Script (64)
- Add node commands to set UZ7HO modem mode and freq (64)
- Trap empty NODECALL or NETROMCALL(65)
- Trap NODES messages with empty From Call (65)
- Add RigControl for SDRConsole (66) // Fix FLRig crash (66)
- Fix VARA disconnect handling (67)
- Support 64 ports (69)
- Fix Node commands for setting UZ7HO Modem (70)
- Fix processing SABM on an existing session (71)
- Extend KISS Node command to send more than one parameter byte (72)
- Add G7TAJ's code to record activity of HF ports for stats display (72)
- Add option to send KISS command to TNC on startup (73)
- Fix Bug in DED Emulator Monitor code (74)
- Add Filters to DED Monitor code (75)
- Detect loss of DED application (76)
- Fix connects to Application Alias with UZ7HO Driver (76)
- Fix Interlock of ports on same UZ7HO modem. (76)
- Add extended Ports command (77)
- Fix crash in Linbpq when stdout is redirected to /dev/tty? and stdin ia redirected (78)
- Fix Web Terminal (80)
- Trap ENCRYPTION message from VARA (81)
- Fix processing of the Winlink API /account/exists response (82)
- Fix sending CTEXT to L4 connects to Node when FULL_CTEXT is not set

### 6.0.23.82 — 2023-08-06

Tag [`6.0.23.82`](https://github.com/g8bpq/linbpq/commit/b77dbd8); `Versions.h` reports `6.0.23.81`.

### 6.0.23.81 — 2023-07-29

Tag [`6.0.23.81`](https://github.com/g8bpq/linbpq/commit/ed81fc5); `Versions.h` reports `6.0.23.77`.

### 6.0.23.77 — 2023-06-29

Tag [`6.0.23.77`](https://github.com/g8bpq/linbpq/commit/75b5bcc); `Versions.h` reports `6.0.23.76`.

### 6.0.23.76 — 2023-06-21

Tag [`6.0.23.76`](https://github.com/g8bpq/linbpq/commit/a21121f); `Versions.h` reports `6.0.23.71`.

### 6.0.23.71 — 2023-05-26

Tag [`6.0.23.71`](https://github.com/g8bpq/linbpq/commit/4924c12); `Versions.h` reports `6.0.23.70`.

### 6.0.23.70 — 2023-05-25

Tag [`6.0.23.70`](https://github.com/g8bpq/linbpq/commit/ac7e6b9); `Versions.h` reports `6.0.23.66`.

### 6.0.23.66 — 2023-05-16

Tag [`6.0.23.66`](https://github.com/g8bpq/linbpq/commit/60ff21f); `Versions.h` reports `6.0.23.59`.

### 6.0.23.59 — 2023-04-06

Tag [`6.0.23.59`](https://github.com/g8bpq/linbpq/commit/f1bf68a); `Versions.h` reports `6.0.23.58`.

### 6.0.23.58 — 2023-04-03

Tag [`6.0.23.58`](https://github.com/g8bpq/linbpq/commit/814c68f); `Versions.h` reports `6.0.23.56`.

### 6.0.23.56 — 2023-03-18

Tag [`6.0.23.56`](https://github.com/g8bpq/linbpq/commit/a792602); `Versions.h` reports `6.0.23.55`.

### 6.0.23.55 — 2023-03-16

Tag [`6.0.23.55`](https://github.com/g8bpq/linbpq/commit/39da8ff); `Versions.h` reports `6.0.23.51`.

### 6.0.23.51 — 2023-03-02

Tag [`6.0.23.51`](https://github.com/g8bpq/linbpq/commit/c32ef4e); `Versions.h` reports `6.0.23.46`.

### 6.0.23.46 — 2023-02-05

Tag [`6.0.23.46`](https://github.com/g8bpq/linbpq/commit/c15de2c); `Versions.h` reports `6.0.23.42`.

### 6.0.23.42 — 2023-01-25

Tag [`6.0.23.42`](https://github.com/g8bpq/linbpq/commit/9a44d00); `Versions.h` reports `6.0.23.36`.

### 6.0.23.36 — 2023-01-06

Tag [`6.0.23.36`](https://github.com/g8bpq/linbpq/commit/90bdcbe); `Versions.h` reports `6.0.23.34`.

### 6.0.23.34 — 2022-12-31

Tag [`6.0.23.34`](https://github.com/g8bpq/linbpq/commit/ebc845e); `Versions.h` reports `6.0.23.33`.

### 6.0.23.33 — 2022-12-09

Tag [`6.0.23.33`](https://github.com/g8bpq/linbpq/commit/e95c1f3); `Versions.h` reports `6.0.23.30`.

### 6.0.23.30 — 2022-11-23

Tag [`6.0.23.30`](https://github.com/g8bpq/linbpq/commit/be0f2b8); `Versions.h` reports `6.0.23.29`.

### 6.0.23.29 — 2022-11-23

Tag [`6.0.23.29`](https://github.com/g8bpq/linbpq/commit/6c6848b); `Versions.h` reports `6.0.23.27`.

### 6.0.23.27 — 2022-11-18

Tag [`6.0.23.27`](https://github.com/g8bpq/linbpq/commit/6c6848b); `Versions.h` reports `6.0.23.27`.

### 6.0.23.26 — 2022-11-14

Tag [`6.0.23.26`](https://github.com/g8bpq/linbpq/commit/e3db09d); `Versions.h` reports `6.0.23.25`.

### 6.0.23.25 — 2022-11-12

Tag [`6.0.23.25`](https://github.com/g8bpq/linbpq/commit/9b5f7cc); `Versions.h` reports `6.0.23.24`.

### 6.0.23.24 — 2022-10-23

Tag [`6.0.23.24`](https://github.com/g8bpq/linbpq/commit/2bd6071); `Versions.h` reports `6.0.23.22`.

### 6.0.23.22 — 2022-10-18

Tag [`6.0.23.22`](https://github.com/g8bpq/linbpq/commit/4a4271c); `Versions.h` reports `6.0.23.21`.

### 6.0.23.21 — 2022-10-03

Tag [`6.0.23.21`](https://github.com/g8bpq/linbpq/commit/9d98903); `Versions.h` reports `6.0.23.18`.

### 6.0.23.20 — 2022-09-22

Tag [`6.0.23.20`](https://github.com/g8bpq/linbpq/commit/9d98903); `Versions.h` reports `6.0.23.18`.

### 6.0.23.18 — 2022-09-07

Tag [`6.0.23.18`](https://github.com/g8bpq/linbpq/commit/e3ea58d); `Versions.h` reports `6.0.23.18`.

---

## Pre-GitHub-mirror upstream history

The upstream GitHub mirror's oldest commit is 6.0.23.18
(September 2022).  Releases before that exist in
[John's NodeChangeLog][nodechangelog] but have no corresponding
tag or commit on the GitHub side.  Folded in below for
completeness, newest first.

### 26 June 2022 Version 6.0.23.1

- Add option to control which applcalls are enabled in VARA
- Add support for rtl_udp to Rig Control
- Fix Telnet Auto Connect to Application when using TermTCP or Web Terminal
- Allow setting css styles for Web Terminal
- And Kill TNC and Kill and Restart TNC commands to Web Driver Windows
- More flexible RigControl for split frequency operation, eg for QO100
- Increase stack size for ProcessHTMLMessage
- Fix HTML Content-Type on images
- Add AIS and ADSB Support
- Compress web pages
- Change minidump routine and close after program error
- Add RMS Relay SYNC Mode
- Changes for compatibility with Winlink Hybrid
- Add Rigcontrol CMD feature to Yaesu code
- Trap potential buffer overrun in ax/tcp code
- Fix possible hang in UZ7HO driver if connect takes a long time to succeed or fail
- Add FLRIG as backend for RigControl
- Fix bug in compressing some management web pages
- Fix bugs in AGW Emulator
- Add more PTT_Sets_Freq options for split frequency working
- Allow RIGCONTROL using Radio Number (Rnn) as well as Port
- Fix Telnet negotiation and backspace processing
- Fix VARA Mode change when scanning
- Add Web Mgmt Log Display
- Fix crash when connecting to RELAY when CMS=0
- Send OK to user for manual freq changes with hamlib or flrig
- Fix Rigcontrol leaving port disabled when using an empty timeband
- Fix processing of backspace in Telnet character processing
- Increase max size of connect script
- Fix HAMLIB Slave Thread control
- Add processing of VARA mode responses and display of VARA Mode
- Fix crash when VARA session aborted on LinBPQ
- Fix handling port selector (2:call or p2 call) on SCS PTC packet ports
- Include APRS Map web page
- Add Enable/Disable to KAMPACTOR scan control (use P0 or P1)
- Add Basic DRATS interface
- Fix MYCALLS on VARA
- Add additonal Rigcontrol options for QO100
- Set Content-Type: application/pdf for pdf files downloaded via web interface
- Fix sending large compressed web messages
- Fix freq display when using flrig or hamlib backends to rigcontrol
- Change VARA Driver to send ABORT when Session Time limit expires
- Add Chat Log to Web Logs display
- Fix possible buffer loss in RigControl
- Allow hosts on local lan to be treated as secure
- Improve validation of data sent to Winlink SessionAdd API call
- Add support for FreeDATA modem.
- Add GetLOC API Call
- Change Leaflet link in aprs map.
- Add Connect Log
- Fix crash when Resolve CMS Servers returns ipv6 addresses
- Fix Reporting P4 sessions to Winlink
- Add support for FreeBSD
- Fix Rigcontrol PTCPORT
- Set TNC Emulator sessions as secure
- Fix not always detecting loss of FLRIG
- Add ? and * wildcards to NODES command
- Add Port RADIO config parameter

### 22 August 2021 Version 6.0.22.1

- Fix bug in KAM TNCEMULATOR
- Add WinRPR Driver (DED HostMode over TCP)
- Fix handling of VARA config commands FM1200 and FM9600
- Improve Web Termanal Line folding
- Add Start TNC to WinRPR driver
- Add support for VARA2750 Mode
- Add support for VARA connects via a VARA Digipeater
- Add digis to SCSTracker and WinRPR MHeard
- Separate RIGCONTROL config from PORT config and add RigControl window on Windows version
- Fix crash when a Windows HID device doesn't have a product_string
- Changes to VARA TNC connection and restart process
- Trigger FALLBACKTORELAY if attempt to connect to all CMS servers fail.
- Fix saving part lines in adif log and Winlink Session reporting
- Add Port Specific CTEXT
- Add FRMR monitoring to UZ7HO driver
- Add audio input switching for IC7610
- Include Rigcontrol Support for IC-F8101E
- Process any response to KISS command
- Fix NODE ADD command
- Add noUpdate flag to AXIP MAP
- Fix clearing NOFALLBACK flag in Telnet Server
- Allow connects to RMS Relay running on another host
- Allow use of Power setting in Rigcontol scan lines for Kenwood radios
- Prevent problems caused by using "CMS" as a Node Alias
- Include standard APRS Station pages in code
- Fix VALIDCALLS processing in HF drivers
- Send Netrom Link reports to Node Map
- Add REALTELNET mode to Telnet Outward Connect
- Fix using S (Stay) parameter on Telnet connects when using CMDPORT and C HOST
- Add Default frequency to rigcontrol to set a freq/mode to return to after a connection
- Fix long (> 60 seconds) scan intervals
- Improved debugging of stuck semaphores
- Fix potential security bug in BPQ Web server
- Send Chat Updates to chatupdate.g8bpq.net port 81
- Add ReportRelayTraffic to Telnet config to send WL2K traffic reports for connections to RELAY
- Add experimental Mode reporting
- Add SendTandRtoRelay param to SCS Pactor, ARDOP and VARA drivers to divert calls to CMS for -T and -R to RELAY
- Add UPNP Support

### 14 December 2020 Version 6.0.21.1

- Fix occasional missing newlines in some node command reponses
- More 64 bit fixes
- Add option to stop setting PDUPLEX param in SCSPACTOR
- Try to fix buffer loss
- Remove extra space from APRS position reports
- Suppress VARA IAMALIVE messages
- Add display and control of QtSoundModem modems
- Only send "No CMS connection available" message if fallbacktorelay is set.
- Add HAMLIB backend and emulator support to RIGCONTROL
- Ensure all beacons are sent even with very short beacon intervals
- Add VARA500 WL2K Reporting Mode
- Fix problem with processing frame collector
- Fix possible problem with interactive RADIO commands not giving a response,
- Incease maximum length of NODE command responses to handle maximum length INFO message,
- Allow WL2KREPORT in CONFIG section of UZ7HO port config.
- Fix program error in processing hamlib frame
- Save RestartAfterFailure option for VARA
- Check callsign has a winlink account before sending WL2KREPORT messages
- Add Bandwidth control to VARA scanning
- Fix TNCPORT reconnect on Linux
- Add SecureTelnet option to limit telnet outward connect to sysop mode sessions or Application Aliases
- Add option to suppress sending call to application in Telnet HOST API
- Add FT991A support to RigControl
- Use background.jpg for Edit Config page
- Send OK response to SCS Pactor commands starting with #
- Resend ICOM PTT OFF command after 30 seconds
- Add WXCall to APRS config
- Fixes for AEAPactor
- Allow PTTMUX to use real or com0com com ports
- Fix monitoring with AGW Emulator
- Derive approx position from packets on APRS ports with a valid 6 char location
- Fix corruption of APRS message lists if the station table fills up.
- Don't accept empty username or password on Relay sessions.
- Fix occasional empty Nodes broadcasts
- Add Digis to UZ7HO Port MH list
- Add PERMITTEDAPPLS port param
- Fix WK2K Session Record Reporting for Airmail and some Pactor Modes.
- Fix handling AX/IP (proto 93) frames
- Fix possible corruption sending APRS messages
- Allow Telnet connections to be made using Connect command as well as Attach then Connect
- Fix Cancel Sysop Signin
- Save axip resolver info and restore on restart
- Add Transparent mode to Telnet Server HOST API
- Fix Tracker driver if WL2KREPORT is in main config section
- SNMP InOctets count corrected to include all frames and encoding of zero values fixed.
- Change IP Gateway to exclude handling bits of 44 Net sold to Amazon
- Fix crash in Web terminal when processing very long lines

### 24 April 2020 Version 6.0.20.1

- Trap and reject YAPP file transfer request
- Fix possible overrun of TCP to Node Buffer
- Fix possible crash if APRS WX file doesn't have a terminating newline
- Change communication with BPQAPRS.exe to restore old message popup behaviour
- Preparation for 64 bit version
- Improve flow control on SCS Dragon
- Fragment messages from network links to L2 links with smaller paclen
- Change WL2K report rate to once every two hours
- Add PASS, CTEXT and CMSG commands and Stream Switch support to TNC2 Emulator
- Add SessionTimeLimit command to HF drivers (ARDOP, SCSPactor, WINMOR, VARA)
- Add links to Ports Web Management Page to open individual Driver windows
- Add STOPPORT/STARTPORT support to ARDOP, KAM and SCSPactor drivers
- Add CLOSE and OPEN RADIO command so Rigcontrol port can be freed for other use
- Don't try to send WL2K Traffic report if Internet is down
- Move WL2K Traffic reporting to a separate thread so it doesn't block if it can't connect to server
- ADD AGWAPPL config command to set application number. AGWMASK is still supported
- Register Node Alias with UZ7HO Driver
- Register calls when UZ7HO TNC Restarts and at intervals afterwards
- Fix crash when no IOADDR or COMPORT in async port definition
- Fix Crash with Paclink-Unix when parsing ; VE7SPR-10 DE N7NIX QTC 1
- Only apply BBSFLAG=NOBBS to APPPLICATION 1
- Add RIGREONFIG command
- fix APRS RECONFIG on LinBPQ
- Fix Web Terminal scroll to end problem on some browsers
- Add PTT_SETS_INPUT option for IC7600
- Add TELRECONFIG command to reread users or whole config
- Enforce PACLEN on UZ7HO ports
- Fix PACLEN on Command Output
- Retry axip resolver if it fails at startup
- Fix AGWAPI connect via digis
- Fix Select() for Linux in MultiPSK, UZ7HO and V4 drivers
- Limit APRS OBJECT length to 80 chars
- UZ7HO disconnect incoming call if no free streams
- Improve response to REJ (no F) followed by RR (F)
- Try to prevent more than MAXFRAME frames outstanding when transmitting
- Allow more than one instance of APRS on Linux
- Stop APRS digi by originating station
- Send driver window trace to main monitor system
- Improve handling of IPOLL messages
- Fix setting end of address bit on dest call on connects to listening sessions
- Set default BBS and CHAT application number and number of streams on LinBPQ
- Support #include in bpq32.cfg processing

### 24 September 2019 Version 6.0.19.1

- Fix UZ7HO interlock
- Add commands to set Centre Frequency and Modem with UZ7HO Soundmodem (on Windows only)
- Add option to save and restore MH lists and SAVEMH command
- Add Frequency (if known) to UZ7HO MH lists
- Add Gateway option to Telnet for PAT
- Try to fix SCS Tracker recovery
- Ensure RTS/DTR is down on CAT port if using that line for PTT
- Experimental APRS Messaging in Kernel
- Add Rigcontrol on remote PC's using WinmorControl
- ADD VARAFM and VARAFM96 WL2KREPORT modes
- Fix WL2K sysop update for new Winlink API
- Fix APRS when using PORTNUM higher than the number of ports
- Add Serial Port Type
- Add option to linbpq to log APRS-IS messages.
- Send WL2K Session Reports
- Drop Tunneled Packets from 44.192 - 44.255
- Log incoming Telnet Connects
- Add IPV4: and IPV6: overrides on AXIP Resolver.
- Add SessionTimeLimit to HF sessions (ARDOP, SCSPactor, WINMOR, VARA)
- Add RADIO FREQ command to display current frequency

### 7 January 2019 Version 6.0.18.1

- Fix validation of NODES broadcasts
- Fix HIDENODES
- Check for failure to reread config on axip reconfigure
- Fix crash if STOPPORT or STARTPORT used on KISS over TCP port
- Send Beacons from BCALL or PORTCALL if configured
- Fix possible corruption of last entry in MH display
- Ensure RTS/DTR is down when opening PTT Port
- Remove RECONFIG command
- Preparations for 64 bit version

### 7 November 2018 Version 6.0.17.1

- Change WINMOR Restart after connection to Restart after Failure and add same option to ARDOP and VARA
- Add Abort Connection to WINMOR and VARA Interfaces
- Reinstate accidentally removed CMS Access logging
- Fix MH CLEAR
- Fix corruption of NODE table if NODES received from station with null alias
- Fix loss of buffer if session closed with something in PARTCMDBUFFER
- Fix spurious GUARD ZONE CORRUPT message in IP Code.
- Remove "reread bpq32.cfg and reconfigure" menu options
- Add support for PTT using CM108 based soundcard interfaces
- Datestamp Telnet log files and delete old Telnet and CMSAcces logs

### 19 March 2018 Version 6.0.16.1

- Fix Setting data mode and filter for IC7300 radios
- Add VARA to WL2KREPORT
- Add trace to SCS Tracker status window and tidy up other status windows
- Fix possible hang in IPGATEWAY
- Add BeacontoIS parameter to APRSDIGI. Allows you to stop sending beacons to APRS-IS.
- Fix sending CTEXT on WINMOR sessions

### 26 February 2018 Version 6.0.15.1

- Partial support for ax.25 V2.2
- Add MHU and MHL commands and MH filter option
- Fix scan interlock with ARDOP
- Add Input source select for IC7300
- Remove % transparency from web terminal signon message
- Fix L4 Connects In count on stats
- Fix crash caused by corrupt CMSInfo.txt
- Add Input peaks display to ARDOP status window
- Add options to show time in local and distances in KM on APRS Web pages
- Add VARA support
- Fix WINMOR Busy left set when port Suspended
- Add ARDOP-Packet Support
- Add Antenna Switching for TS 480
- Fix possible crash in Web Terminal
- Support different Code Pages on Console sessions
- Use new Winlink API interface (api.winlink.org)
- Support USB/ACC switching on TS590SG
- Fix scanning when ARDOP or WINMOR is used without an Interlocked Pactor port.
- Set NODECALL to first Application Callsign if NODE=0 and BBSCALL not set.
- Add RIGCONTROL TUNE and POWER commands for some ICOM and Kenwwod rigs
- Fix timing out ARDOP PENDING Lock
- Support mixed case WINLINK Passwords
- Add TUNE and POWER Rigcontol Commands for some radios
- ADD LOCALTIME and DISPKM options to APRS Digi/Igate

### 12 July 2017 Version 6.0.14.1

- Fix Socket leak in ARDOP and FLDIGI drivers.
- Add option to change CMS Server hostname
- ARDOP Changes for 0.8.0+
- Discard Terminal Keepalive message (two nulls) in ARDOP command hander
- Allow parameters to be passed to ARDOP TNC when starting it
- Fix Web update of Beacon params
- Retry connects to KISS ports after failure
- Add support for ARDOP Serial Interface Native mode.
- Fix gating APRS-IS Messages to RF
- Fix Beacons when PORTNUM used
- Make sure old monitor flag is cleared for TermTCP sessions
- Add CI-V antenna control for IC746
- Don't allow ARDOP beacons when connected
- Add support for ARDOP Serial over I2C
- Fix possble crash when using manual RADIO messages
- Save out of sequence L2 frames for possible euse after retry
- Add KISS command to send KISS control frame to TNC
- Stop removing unused digis from packets sent to APRS-IS
- Processing of ARDOP PING and PINGACK responses
- Handle changed encoding of WL2K update responses.
- Allow anonymous logon to telnet
- Don't use APPL= for RP Calls in Dragon Single mode.
- Add basic messaging page to APRS Web Server
- Add debug log option to SCSTracker and TrkMulti Driver
- Support REBOOT command on LinBPQ
- Allow LISTEN command on all ports that support ax.25 monitoring

### 27 September 2016 Version 6.0.13.1

- Allow /ex to exit UNPROTO mode
- Support ARDOP ARQBW commands
- Support IC735
- Fix sending ARDOP beacons after a busy holdoff
- Enable BPQDED driver to beacon via non-ax.25 ports
- Fix channel number in UZ7HO monitoring
- Add SATGate mode to APRSIS Code
- Fix crash caused by overlong user name in telnet logon
- Add option to log L4 connects
- Add AUTOADDQuiet mode to AXIP
- Add EXCLUDE processing
- Support WinmorControl in UZ7HO driver and fix starting TNC on Linux
- Convert calls in MAP entries to upper case
- Support Linux COM Port names for APRS GPS
- Fix using NETROM serial protocol on ASYNC Port
- Fix setting MYLEVEL by scanner after manual level change
- Add DEBUGLOG config param to SCS Pactor Driver to log serial port traffic
- Use #myl to set SCS Pactor MYLEVEL, and add checklevel command
- Add Multicast RX interface to FLDIGI Driver
- Fix processing application aliases to a connect command
- Fix Buffer loss if radio connected to PTC rig port but BPQ not configured to use it
- Save backups of bpq32.cfg when editing with Web interface and report old and new length
- Add DD command to SCS Pactor, and use it for forced disconnect
- Add ARDOP mode select to scan config
- ARDOP changes for ARDOP V 0.5+
- Flip SSID bits on UZ7HO downlink connects
- Force L2 connect to call in NODES table if call preceeded with ! (eg C 2 !g8bpq)

### 2nd November 2015 Version 6.0.12.1

- Fix logging of IP addresses for connects to FBBPORT
- Allow lower case user and passwords in Telnet "Attach and Connect"
- Fix possible hang in KISS over TCP Slave mode
- Fix duplicating LinBPQ process if running ARDOP fails
- Allow lower case command aliases and increase alias length to 48
- Fix saving long IP frames pending ARP resolution
- Fix dropping last entry from a RIP44 message.
- Fix displaying Digis in MH list
- Add port name to Monitor config screen port list
- Add KISSOPTIONS TRACKER to allow SCS Tracket to be used in KISS Mode
- Fix APRS command call filter and add port filter
- Support port names in BPQTermTCP Monitor config
- Add FINDBUFFS command to dump lost buffers to Debugview/Syslog
- Buffer Web Mgmt Edit Config output
- Add WebMail Support
- Fix not closing APRS Send WX file.
- Add RUN option to APRS Config to start APRS Client
- LinBPQ runs FindLostBuffers and exits if QCOUNT < 5
- Close ARDOP and restart connection if nothing received for 90 secs
- Add option to bridge all packets between ports (not just APRS UI frames)

### 10th September 2015

- Version 6.0.11.1
- Fixes for IPGateway configuration and Virtual Circuit Mode
- Separate Portmapper from IPGateway
- Add PING Command
- Add ARDOP Driver
- Add basic APPLCALL support for PTC-PRO/Dragon 7800 Packet (using MYALIAS)
- Add "VeryOldMode" for KAM Version 5.02
- Add KISS over TCP Slave Mode.
- Support Pactor and Robust Packet on same port on P4Dragon
- Add "Remote Station Quality" to Web ROUTES display
- Add AMPRNet (Net44) Tunneling and RIP44 process
- Add NAT for local hosts to IPGateway
- Fix setting filter from RADIO command for IC7410
- Add Memory Channel Scanning for ICOM Radios
- Try to reopen Rig Control port if it fails (could be unplugged USB)
- Fix restoring position of Monitor Window
- Stop Codec on Winmor and ARDOP when an interlocked port is attached (instead of listen false)
- Support APRS beacons in RP mode on Dragon
- Change Virtual MAC address on IPGateway to include last octet of IP Address
- Fix "NOS Fragmentation" in IP over ax.25 Virtual Circuit Mode
- Fix sending I frames before L2 session is up
- Fix Flow control on Telnet outbound sessions.
- Fix reporting of unterminatred comments in config
- Add option for RigControl to not change mode on FT100/FT990/FT1000
- Add "Attach and Connect" for Telnet ports

### 14th February 2015

- Version 6.0.10.1
- Fix crash if corrupt HTML request received.
- Allow SSID's of 'R' and 'T' on non-ax.25 ports for WL2K Radio Only network.
- Make HTTP server HTTP Version 1.1 complient - use persistent conections and close after 2.5 mins
- Add INP3ONLY flag.
- Fix program error if UNPROTO command entered without a destination path
- Show client IP address on HTTP sessions in Telnet Server
- Reduce frequency and number of attempts to connect to routes when Keepalives or INP3 is set
- Add FT990 RigControl support, fix FT1000MP support.
- Support ARMV5 processors
- Changes to support LinBPQ APRS Client
- Add IC7410 to supported Soundcard rigs
- Add CAT PTT to NMEA type (for ICOM Marine Radios
- Fix KISS ACKMODE
- Add KISS over TCP
- Support ACKMode on VKISS
- Improved reporting of configuration file format errors
- Experimental driver to support ARQ sessions using UI frames

### 26th October 2014

- Version 6.0.9.1
- Fix setting NOKEEPALIVE flag on route created from imcoming L3 message
- Ignore NODES from locked route with quality 0
- Fix seting source port in AXIP
- Fix Dual Stack (IPV4/V6) on Linux.
- Fix RELAYSOCK if IPv6 is enabled.
- Add support for FT1000
- Fix hang when APRS Messaging packet received on RF
- Attempt to normalize Node qualies when stations use widely differing Route qualities
- Add NODES VIA command to display nodes reachable via a specified neighbour
- Fix applying "DisconnectOnClose" setting on HOST API connects (Telnet Server) Fix buffering large messages in Telnet Host API
- Fix occasional crash in terminal part line processing
- Add "NoFallback" command to Telnet server to disable "fallback to Relay"
- Improved support for APPLCALL scanning with Pactor
- MAXBUFFS config statement is no longer needed.
- Fix USEAPPLCALLS with SCS Tracker when connect to APPLCALL fails
- Implement LISTEN and CQ commands
- FLDIGI driver can now start FLDIGI on a remote system
- Add IGNOREUNLOCKEDROUTES parameter

### 17th August 2014

- Version 6.0.8.1
- Use Registry Key HKEY_CURRENT_USER on all OS versions
- Fix crash when APRS symbol is a space.
- Fixes for FT847 CAT
- Fix display of 3rd byte of FRMR
- Add "DEFAULT ROBUST" and "FORCE ROBUST" commands to SCSPactor Driver
- Fix possible memory corruption in WINMOR driver
- Fix FT2000 Modes
- Use new WL2K reporting system (Web API Based)
- APRS Server now cycles through hosts if DNS returns more than one
- BPQ32 can now start and stop FLDIGI
- Fix loss of AXIP Resolver when running more than one AXIP port
- mplement LISTEN and CQ commands

### 13th April 2014

- Version 6.0.7.1
- FLDigi now checks for busy before allowing an outgoing connect

### 1st April 2014 Version

- 6.0.6.1
- Added FLDigi Interface See here for details.
- Fix "All CMS Servers are inaccessible" message so Mail Forwarding ELSE works.
- Validate INP3 messages to try to prevent crash
- Fix possible crash if an overlarge KISS frame is received
- Fix error in AXR command
- Add LF to Telnet Outward Connect signin if NEEDLF added to connect line
- Add CBELL to TNC2 emulator
- Add sent objects and third party messages to APRS Dup Check List
- Incorporate UIUtil in BPQ32.dll
- Fix TNC State Display for Tracker
- Cache CMS Addresses on LinBPQ
- Fix count error on DED Driver when handling 256 byte packets
- Add basic SNMP interface for MRTG
- Fix memory loss from getaddrinfo
- Process "BUSY" response from Tracker
- Handle serial port writes that don't accept all the data (could cause truncated packets)

### 4th January 2014

- Version 6.0.5.1
- Add "Clear" option to MH command
- Add "Connect to RMS Relay" Option
- Revert to one stop bit on serial ports, explictly set two on FT2000 rig control
- Fix routing of first call in Robust Packet
- Add Options to switch input source on rigs with build in soundcards (so far only IC7100/7200 and Kenwood 590)
- Add RTS>CAT PTT option for Sound Card rigs
- Add Clear Nodes Option (NODE DEL ALL)
- SCS Pactor can set differeant APPLCALLS when scanning.
- Fix possible Scan hangup after a manual requency change with SCS Pactor
- Accept Scan entry of W0 to disable WINMOR and P0 to disable Pactor on that frequency
- Fix corruption of NETROMCALL by SIMPLE config command
- Enforce Pactor Levels
- Add Telnet outward connect
- Add Experimantal RMS Relay/Trimode Emulation (Not complete yet)
- Fix V4 Driver
- Add PTT Mux (so more than one sound card mode can use the same radio)
- Add Locked ARP Entries (via bpq32.cfg)
- Fix IDLETIME node command
- Fix STAY param on connect
- Add STAY option to Attach and Application Commands
- Fix crash on copying a large AXIP MH Window
- Fix possible crash when bpq32.exe dies
- Fix DIGIPORT for UI frames

### 6th October 2013

- Version 6.0.4.1
- Add frequency dependent autoconnect appls for Pactor
- Fix DED Monitoring of I and UI with no data
- Include AGWPE Emulator (from AGWtoBPQ)
- Accept DEL (Hex 7F) as backspace in Telnet
- Fix re-running resolver on re-read AXIP config
- Speed up processing, mainly for Telnet Sessions
- Fix APRS init on restart of bpq32.exe
- Change serial port setup to 2 stop bits
- Fix scrolling of WINMOR trace window
- Fix Crash when ueing DED TNC Emulator
- Fix Disconnect when using BPQDED2 Driver with Telnet Sessions
- Allow HOST applications even when CMS option is disabled
- Fix APRS DIGIMAP command with no targets (didn't suppress default settings)

### 17th July 2013 Version

- 6.0.3.1
- Add facility to start amd kill a WINMOR TNC on a remote host
- Fix Program Error when APRS Item or Object name is same as call of reporting station
- Don't digi a frame that we have already digi'ed
- Add ChangeSessionIdleTime API
- Add WK2KSYSOP Command
- Add IDLETIME Command
- Fix Errors in RELAYAPPL processing
- Add STOPPORT and STARTPORT commands to close/reopen KISS ports so TNC can be reconfigured without closing node
- Fix possible crash caused by invalid RIGCONFIG line
- The documentation of Node User and SYSOP commands has been updated

### 6th June 2013 Version

- 6.0.2.1
- Fix operation on Win98
- Fix callsign error with AGWtoBPQ
- Fix PTT problem with WINMOR
- Fix Reread telnet config
- Add Secure CMS signon
- Fix error in cashing addresses of CMS servers
- Fix Port Number when using Send Raw.
- Fix PE in KISS driver if invalid subchannel received
- Fix Origin address of beacons
- Speed up Telnet port monitoring.
- Add TNC Emulators. See here for details
- Add CountFramesQueuedOnStream API
- Add XDIGI feature. See here for details
- Add Winmor Robust Mode switching for compatibility with new Winmor TNC
- Add APRS packet decode and Web Interface
- APRS Digi/Igate can now gate packets from APRS-IS to RF - please use with caution!
- Stop corruption caused by overlong KISS frames

### 22th March 2013

- Version 6.0.1.1
- Now available for Linux systems (LinBPQ) as well as Windows. See here for more information.
- New KISSOPTIONS:
- PITNC
- NOPARAMS - Don't send Parameters (TXDELAY, SLOTTIME, etc) to TNC;
- Optional L2 Alias can be specified on APPLICATION config statement
- Add "KISS over UDP" driver.
- Add option to bridge APRS frames from one port to another. Mainly to allow uising 3rd party APRS clients with BPQ32 APRS Digi/IGate
- Web Interface includes Drivr and Stream Status Windows.
- TCP/IP API added - mainly for LinBPQ, but also available on Windows version See here for details.

### 25th September 2012

- Version 5.2.9.1
- Fix possible crash when using KISS ports with COMn > 16

### 8nd August 2012

- Version 5.2.8.1
- Fix handling TelnetServer packets over 500 bytes in normal mode
- Fix Igate handling packets from UIView
- Prototype Baycom driver (not yet fully functional)
- Set WK2K group ref to MARS (3) if using a MARS service code
- Various bug fixes to reduce random crashes/hangs
- Add TNCX KISSOPTION for TNC-X BPQKISS software (includes the ACKMODE bytes in the checksum)

### 2nd June 2012 Version

- 5.2.7.1
- Fix opening more thn one console window on Win98
- Change method of configuring multiple timelots on WL2K reporting (use : to separate)
- Add option to update the WK2K Sysop Database
- Add Web server
- Add UIONLY port option

### 2nd April 2012 Version

- 5.2.6.1
- Convert to MDI (Multiple Docment Interface) presentation of BPQ32.dll windows. See here for details
- Add option to send APRS Objects and Items
- Send APRS Status packets
- Send QUIT not EXIT in SCS PTC Initialisation sequence
- Implement new WL2K reporting format and include traffic reporting info in CMS signon
- New formet for WL2KREPORT Configuration Statement. See here for details
- Prevent loops when APPL alias refers to itself
- Add RigControl for Flex and ICOM IC-M710 Marine radios

### 17th February 2012

- Version 5.2.5.1
- Don't look for Password file. Password is now specified in BPQ32.cfg
- Add extra MultiPSK commands for control of ALE Beacons and Mode changes
- Fix MultiPSK Transparency. MultiPSK can now be used for binary transfers
- Make LOCATOR command compulsory
- Add MobileBeaconInterval APRS param
- Send Course and Speed when APRS is using GPS
- Fix Robust Packet reporting in PTC driver when some channels are Pactor only
- Fix corruption of some MIC-E packets by APRS code

### 29th January 2012

- Version 5.2.4.1
- Remove CR from Telnet User and Password Prompts
- Add Rigcontrol to UZ7HO driver
- Fix corruption of Free Buffer Count by Rigcontol
- Fix WINMOR and V4 PTT
- Add MultiPSK Driver (for ALE400 and 141A modes)
- Remove need for MAP DUMMY in AXIP config (for Chat Map)
- Fix check on length of Port Config ID String with trailing spaces
- Fix interlock when Port Number is not equal to the port position in config filet
- Add optional NETROMCALL for L3 Activity
- Fix Telnet you dont have a TCPPORT and use FBBPORT
- Add Reread APRS Config command to BPQ32 Console
- Fix switching to Pactor after scanning in normal packet mode (SCSPTC Driver)
- Add Support for BPQAPRS - an APRS Mapping and Messaging Application
- Add IPV6 support to APRS IGate

### 4th January 2012

- Version 5.2.3.1
- If you use RigControl, please read this, before installing this version, as the configuration format has changed.
- If you are currently running a version below 5.2.1.3, please read warming at the start of the 5.2.1.3 Changelog.
- Rewrite RigControl and add "Reread RigControl Config"
- Connects from the console to an APPLCALL or APPLALIAS now invoke any Command Alias that has been defined.
- Fix reporting of Tracker freqs to WL2K.
- Fix Tracker monitoring setup (sending M UISC)
- Fix possible call/application routing error on RP
- Changes for P4Dragon
- Supports User Mode VCOM Driver for VKISS Ports
- Include APRS Digi/IGate
- Tracker monitoring now includes DIGIS
- Include driver for UZ7HO soundcard modem.
- Support sending UI frames using SCSTRACKER, SCTRKMULTI and UZ7HO drivers
- Accept DRIVER as an alternative to DLLNAME, and COMPORT as an alternative to IOADDR in bpq32.cfg. COMPORT is decimal
- No longer supports separate config files, or BPQTELNETSERVER.exe
- Improved flow control for Telnet CMS Sessions
- Fix handling Config file without a newline after last line
- Add non - Promiscuous mode option for BPQETHER
- Change Console Window to a Dialog Box.
- Fix possible corruption and loss of buffers in Tracker drivers
- Add "Beacon After Session" option to Tracker and UZ7HO Drivers
- Add option to add comments to the NodeMap

### 17th October 2011

- Version 5.2.1.3
- WARNING!!!! If you use VISTA or WIN7, the first time you run this version, your registry configuration for all BPQ32 programs will be moved from HKEY_LOCAL_MACHINE to HKEY_CURRENT_USER.
- This is necessary as I've found that Vista/WIN7 stores HKEY_LOCAL_MACHINE in an obscure place unless you are running as administrator. This messes up the Registry Save/Restore process.
- Add caching of CMS Server IP addresses. This enables CMS Telnet to function during a DNS outage.
- Initialise TNC State on Pactor Dialogs. The TNC State wasn't always shown correctly.
- Add Shortened (6 digit) AUTH mode. Supports BPQAuth, a new method for BBS SYSOP Authentication over radio links.
- Update MH with all frames (not just I/UI). MH didn't used to update on connect requrests, etc.
- Add IPV6 Support for TelnetServer and AXIP.
- Fix TNC OK Test for Tracker. You could sometimes attach a Tracker port, even if the link to TNC was down.
- Fix crash in CMS mode if terminal disconnects while tcp connect in progress.
- Add WL2K reporting for Robust Packet.
- Add option to suppress WL2K reporting for specific frequencies.
- Fix Timeband processing for Rig Control. Having more that two timebands didn't always work properly.
- New Driver for SCS Tracker allowing multiple connects, so Tracker can be used for user access. See SCSTrackerMulti.
- Experimental Driver for V4 TNC. V4 is a narrowband soundcard mode from the author of WINMOR.
- Combine busy detector on Interlocked Ports (SCS PTC, WINMOR or KAM)
- Improved program error logging
- WL2K reporting format changed. This should allow BPQ32 stations to appear on the Winlink HF Status page

### 11th April 2011

- Version 5.0.0.1
- Add "Close all programs" command
- Add BPQ Program Directory registry key, so software and config can be placed in different directories
- Time out IP Gateway ARP entries, and only reload ax.25 ARP entries from BPQARP.DAT
- Add support for SCS Tracker HF Modes
- Fix WL2K Reporting for Packet Sessions
- Report software version to WL2K when using Telnet CMS Mode

### 14th February 2011

- Version 4.10.16.15
- Add support for BPQTermTCP, a new program for remote accesss to a BPQ32 Node over the Internet
- Allow TelnetServer to listen on more that one port in FBB Mode.
- Allow Telnet FBB mode sessions to send CRLF as well as CR on user and pass msgs, simplifiying use with WinPack
- Add session length to CMS Telnet logging.
- Show uptime in Days/Hours/Minutes instead of minutes

### 20th January 2011

- Version 4.10.16.13
- Fix loss of buffers in TelnetServer causing Node to hang.
- Add logging of CMS Telnet sessions.
- Add non - Promiscuous mode option for BPQETHER, for use with cards that don't support Promiscuous mode
- Add option for Hardware PTT to use a different com port from the scan port
- Add CAT PTT for Yaesu 897
- Fix RMS Packet ports reporting busy after restart or reconfiguration of RMS Packet
- Fix CMS Telnet with MAXSESSIONS > 10

### 5th January 2011

- Version 4.10.16.11
- Fix MH Update for SCS Outgoing Calls
- Allow BPQ32 to access the WL2K CMS Servers via TelnetServer (Instead of via RMS Packet)
- Fix occasional Program Error when a Pactor or Winmor session disconnects with data outstanding.

### 20th December 2010

- Version 4.10.16.10
- Fix freq display for FT100 (was KHz, not MHz)
- Allow Map reporting position to be set using Lat/Lon as well as Locator. See here for details.
- Fix Telnet Log Name
- Fix starting with Minimized windows when Minimizetotray isn't set
- Support SCS Robust Packet Mode on some SCS PTC Controllers. See here for details. Robust Packet support is still experimental.
- Add support for FT2000 to Rigcontrol
- Only Send CTEXT to connects to Node (not to connects to an Application Call)

### 16th November 2010

- Version 4.10.16.8
- Include support for HAL Clover/Pactor Modems
- Changes to Pactor Drivers disconnect code
- AXIP now sends with source port = dest port, unless overridden by SOURCEPORT param. See here for details.
- Config now checks for duplicate port definitions
- Add Node Map reporting
- Fix WINMOR deferred disconnect.
- Write Telnet log to BPQ Directory
- Add Port to AXIP resolver display
- Add support for FT100 to Rigcontrol
- Add "Save Registry Config" command to "Actions" menu
- The AEA PK232 Pactor driver is no longer considered experimental.

### 14th October 2010

- Version 4.10.16.5
- Fix problem with loading on Win98/ME systems.
- Fix problem wirh re-reading AXIP Resolver config.
- Support more than one AXIP Port
- Move TelnetServer into bpq32.dll. See here for details.
- Report AXIP accept() fails to syslog, not a popup.
- AEA Pactor driver is included in bpq32.dll, but this driver is still considered experimental.

### 7th October 2010

- Version 4.10.16.3
- Rigcontrol has been rewritten, with new options, such as setting Winmor/Pactor session bandwidth, ICOM Repeater Shift and Data Mode and Antenna Switching. Configuration is now in the driver config, and there is no separate RigControl window - the info appears in the Pactor/Winmor windows. See the RigControl documentation for details
- Most drivers previously provided as .dll files are now built in to bpq32.dll. However, you still configure them the same - TYPE=EXTERNAL DLLNAME=xxxxx.dll.
- Extend INFOMSG to 2000 bytes
- Improve Scan freq change lock (check both SCS and WINMOR Ports)
- Add option to reread IP Gateway config.
- Fix extra entries being left in window list after reinitialisation.
- If you are using WINMOR, you can now get bpq32 to start the TNC, and close it when BPQ32 exits. See the WINMOR documentation for details.
- The WINMOR and Pactor drivers now include most configuration commands, Only site-specific customisation is needed in the config files. See the documentation for each driver for details.
- You can now included all driver configuration information in bpq32.cfg. Just before the ENDPORT add CONFIG, then the config statements from your driver.cfg file, eg:
- PORT ID=AXIP Link TYPE=EXTERNAL DLLNAME=BPQAXIP.DLL QUALITY=200 MAXFRAME=4 FRACK=5000 RESPTIME=1000 RETRIES=10 PACLEN=236 MINQUAL=150 UNPROTO=FBB ; DEFAULT UNPROTO ADDR BCALL=GM8BPQ ; Call for Beacons
- CONFIG
- BROADCAST NODES MHEARD ON
- UDP 10093 ;Listens for UDP packets on this port number
- AUTOADDMAP MAP GM8BPQ 192.168.0.101 UDP 10093 B MAP DUMMY bpqchatmon.ham-radio-op.net UDP 10090 B
- ENDPORT
- You can still have separate config files, but I recommend converting to the new format.
- The configuration for the WINMOR and Pactor drivers is a bit different when the config in bpq32.cfg - see the documentation for each driver for details.

### 16th August 2010

- Version 4.10.15.4
- New Configuration file documentation here.
- Read bpq32.cfg (or bpqcfg.txt) instead of bpqcfg.bin
- Support 32 bit MMASK (Allowing 32 Ports)
- Support 32 bit APPLMASK (Allowing 32 Applications)
- Allow longer Application command aliases (up to 32 bytes)
- Fix logic error in RIGControl Port Initialisation (wasn't always raising RTS and DTR)
- Clear RIGControl RTS and DTR on close
- Fix Kenwood Rig Control when more than one message received at once.
- Save minimzed state of Rigcontrol Window
- Fix reporting of set errors in scan to a random session
- Now returns "Sorry, Application XXX is not running - Please try later" instead of "Sorry, All XXX Ports are in use - Please try later" if Application isn't running.

### 2nd June 2010

- Version 4.10.14.3
- Add option to prevent node trying to keep link to a neighbours open.

### 6th April 2010

- Version 4.10.14.2
- No longer flips SSID bits on Downlink Connect if uplink is Pactor/WINMOR
- Fix resetting IDLE Timer on Pactor/WINMOR sessions. This was preventing transfers lasting more than 15 minutes
- Add KISS OPTION "D700" which removes risk of accidentally taking D700/D710 radios out of KISS Mode

### 20th March 2010

- Version 4.10.14.1
- Rig Control is now build in to bpq32.dll. Rigcontrol.dll is no longer used.
- Adds control of Kenwood Rigs
- Adds option to combine Attach and Call commands for Pactor and WINMOR
