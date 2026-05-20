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
  with a clean disconnect instead of an out-of-bounds path scan
  (`AGWAPI.c::ProcessAGWCommand`).
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
  now validated to be alphanumeric + spaces only.  Closes the
  shell-injection vector tracked in
  [#30](https://github.com/M0LTE/linbpq/issues/30)
  (`BBSUtilities.c::run_pg`).
- **NET/ROM**: null-pointer guards added around route-structure
  dereferences (`BPQINP3.c`).
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

Earlier upstream releases predate this fork's release-tracking
scheme and aren't documented here individually — see
[upstream's NodeChangeLog][nodechangelog] for full history.

[6.0.25.23]: https://github.com/g8bpq/linbpq/commit/225fbb1
