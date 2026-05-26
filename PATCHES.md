# Patch Tracking

This branch (`patched`) carries local fixes rebased on top of `master`.
Each patch is a single squashed commit. When John merges an upstream fix
for the same issue, the corresponding patch should be dropped on the next
rebase.

| # | Commit subject | Severity | Upstream PR | Upstream Issue | Status |
|---|---------------|----------|-------------|----------------|--------|
| 1 | Fix assignment-instead-of-comparison in L3TRYNEXTDEST | Critical | [#50](https://github.com/M0LTE/linbpq/pull/50) | [#57](https://github.com/M0LTE/linbpq/issues/57) | pending |
| 2 | Fix wrong array indexing in CLEARACTIVEROUTE | Critical | [#51](https://github.com/M0LTE/linbpq/pull/51) | [#58](https://github.com/M0LTE/linbpq/issues/58) | pending |
| 3 | Fix Route pointer corruption in sendAlltoOneNeigbour | Significant | [#53](https://github.com/M0LTE/linbpq/pull/53) | [#60](https://github.com/M0LTE/linbpq/issues/60) | pending |
| 4 | Fix bare QTSM command crashing user session (NULL deref in QTSMCMD) | Significant | [#65](https://github.com/M0LTE/linbpq/pull/65) | [#64](https://github.com/M0LTE/linbpq/issues/64) | pending |
| 5 | Remove dead unsigned < 0 comparison in ProcessRTTReply | Minor | [#55](https://github.com/M0LTE/linbpq/pull/55) | [#62](https://github.com/M0LTE/linbpq/issues/62) | pending |
| 6 | Remove redundant ROUTEPTR++ in UpdateNode loop | Minor | [#56](https://github.com/M0LTE/linbpq/pull/56) | [#63](https://github.com/M0LTE/linbpq/issues/63) | pending |

## Dropped — false positives confirmed by upstream

| Subject | Upstream PR | Why dropped |
|---------|-------------|-------------|
| Fix RTTIncrement to include NeighbourSRTT | [#52](https://github.com/M0LTE/linbpq/pull/52) | G8BPQ confirmed: docs error, not code error.  Since clocks aren't synchronised, RTT is always a locally-measured full round-trip; averaging ours and the neighbour's measurements adds no information.  The `asmstrucs.h` comment claiming the average was misleading; the code is correct. |
| Fix wrong RouteLastTT index in RIF send functions | [#54](https://github.com/M0LTE/linbpq/pull/54) | G8BPQ confirmed: dead code path — RTT is incremented at the receiving end now (XR compatibility), so there is no separate last-value per route to index.  Our patch targeted a code path no longer reached. |

## Status values

- **pending** — fix not yet merged upstream; our patch is active
- **superseded** — upstream merged a fix; drop this patch on next rebase
