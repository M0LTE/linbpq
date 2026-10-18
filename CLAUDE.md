# LinBPQ Fork — Development Guide

## Branch strategy

- **`master`** - John G8BPQ's official LinBPQ plus a small number of
  fork changes. It is the only long-lived branch.

Fork changes are fixes worth carrying before John releases them (for
example #71, the KISS-over-TCP start-up crash) and features he may never
take (for example #76, BBS session limits and channel interlock). Offer
each one to John, and drop it when one of his releases includes it.

- Keep each change to as few commits as possible (ideally one) so it's
  easy to find, re-apply and drop. Don't rewrite master to squash
  later fixes in; list the extra commits in `fork-changes.md`.
- Put new code in its own file, with short hooks in John's files, so
  release syncs conflict on as few lines as possible (see
  `BBSSessionControl.c`). Don't reformat or tidy John's code around a
  hook.
- List every carried change in `docs/project/fork-changes.md`, and
  follow its checklist at each release sync.

The `patched` branch used to carry fixes separately. It was retired on
2026-09-29 once John had taken most of them, and is archived as the tag
`archive/patched`.

## Releases

Each of John's releases is applied to master as one
`upstream: apply g8bpq/linbpq <version>` commit. Before tagging, check
that the `tests` workflow passed on master for the newest commit that
changed code. Docs-only commits, such as release notes, don't run it,
and publishing doesn't wait for it, so a sync that broke a fork change
would otherwise ship. Tagging master
`v<version>` (matching `KVerstring` in `Versions.h`) publishes the
`m0lte/linbpq:<version>` image, moves `latest`, and deploys the versioned
docs. The image is built from master, so it includes any fork changes
carried at the time.

## Building

```bash
make -j$(nproc)
```

Requires: libpaho-mqtt-dev, libjansson-dev, libminiupnpc-dev,
libconfig-dev, libpcap-dev, zlib1g-dev, libbacktrace-dev (not packaged
for Debian 12 or Ubuntu 24.04; see docker/Dockerfile for a source build).

## Integration tests

Python-based integration tests live in `tests/integration/` and run via
Docker (see `.github/workflows/tests.yml`). These test full LinBPQ
instances.
