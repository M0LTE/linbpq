# Fork changes

The code in this fork is John Wiseman G8BPQ's
[`g8bpq/linbpq`][upstream] plus the changes below. The
`m0lte/linbpq` image is built from this fork, so it includes
them.

Each change is kept to as few commits on `master` as possible
(ideally one), so it's easy to find, re-apply or drop. Changes are offered to John. When one of his
releases includes a change, the fork drops its own copy at that
release sync and the entry moves to the bottom table.

The tests, docs, Docker and CI files are fork-only and aren't
listed here.

[upstream]: https://github.com/g8bpq/linbpq

## Carried

| Change | Kind | Commits | Code | Offered to John | Notes |
|---|---|---|---|---|---|
| BBS session time limits and channel interlock for partner forwarding ([#76][pr76], [#80][pr80]) | Feature | `f2bb0c8` | `BBSSessionControl.c`, hooks in `BBSUtilities.c` and `L2SABM` in `L2Code.c`, web config in `BBSHTMLConfig.c` and `templatedefs.c` | Not yet | Incoming `INTERLOCK`, `INTERLOCK GROUP <n>`, `MaxSessionTime` / `SessionLockout`, session-length logging, and partner link requests the BBS would refuse answered with DM. See [Inter-BBS forwarding](../subsystems/bbs-forwarding.md). Tests: `tests/integration/test_bbs_session_limits.py`, `tests/integration/test_bbs_link_refusal.py`. |
| L2: discard repeated I frames outside the receive window ([#81][pr81], packet-net/dapps#425) | Fix | one, in [#81][pr81] | `SDIFRM` in `L2Code.c` | Not yet | Repeats were saved as future frames: SREJ for a frame never sent, then stale data delivered as new on 2.2 links. Test: `tests/integration/test_l2_sequence_errors.py` (`dup`). |
| L2: reset the link on an invalid N(R) ([#81][pr81]) | Fix | one, in [#81][pr81] | `SDFRMR` in `L2Code.c` | Not yet | FRMRHACK left the link silent until it retried out. Test: same file (`badnr`). |
| L2: count only poll answers towards "Too many repeats of same I frame" ([#81][pr81]) | Fix | one, in [#81][pr81] | `SFRAME` and `ACKMSG` in `L2Code.c` | Not yet | A burst of frames with no new ack disconnected a healthy link. Test: same file (`counter`). |

[pr76]: https://github.com/M0LTE/linbpq/pull/76
[pr80]: https://github.com/M0LTE/linbpq/pull/80
[pr81]: https://github.com/M0LTE/linbpq/pull/81

## Taken by John

| Change | Kind | Fork commit | Dropped at |
|---|---|---|---|
| KISS over TCP start-up crash ([#71][pr71]) | Fix | `edcc798` | 6.0.26.1, which fixes it the same way |

[pr71]: https://github.com/M0LTE/linbpq/pull/71

## At each release sync

1. Apply John's release as usual.
2. For each carried change, check whether his release includes it.
   If it does, take his version, drop the fork's, and move the
   entry to "Taken by John".
3. For the rest, check the hooks survived any conflicts, then let
   CI run the integration suite before tagging.
4. Mention carried changes that are new since the last release in
   that release's notes.
