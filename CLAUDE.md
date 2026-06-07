# LinBPQ Fork — Development Guide

## Branch strategy

This fork uses two long-lived branches:

- **`master`** — clean mirror of upstream (John G8BPQ's official LinBPQ).
  Never commit local patches here. Only upstream syncs and docs/CI changes
  that don't touch LinBPQ source code.

- **`patched`** — our distribution branch. Carries local bug fixes rebased
  on top of master. Has its own releases (binary + Docker). Each patch is
  a single squashed commit with an `Upstream: PR #N, Issue #N` trailer.
  See `CLAUDE.md` and `PATCHES.md` on the `patched` branch for full
  details on adding, dropping, rebasing patches, tagging releases, and
  the Docker image tag scheme.

### Rules

1. **Do not commit source fixes to master.** Propose them as PRs against
   master (so John can review), but land them on `patched` only.
2. **Each patch = one squashed commit.** Keep patches atomic and
   independent so they can be dropped individually.
3. **Order patches by severity:** critical first, then significant, then
   minor. This keeps the most important fixes closest to the base.

## GitHub authorship (standing instruction)

Anything posted to GitHub through this assistant goes out under Tom's
(M0LTE's) account, so it must be **explicit that Claude — Tom's AI
assistant — wrote it, not Tom.** This applies to issues, pull requests,
issue/PR comments, and reviews.

- Never write in the first person as Tom.
- Add a clear attribution, e.g. an italic sign-off:
  `— Written by Claude, Tom's (M0LTE) AI assistant, on his behalf.`
- When drafting on Tom's behalf, write in the assistant's own voice
  ("I traced…", "I'd recommend…") rather than impersonating him.

## Building

```bash
make -j$(nproc)
```

Requires: libpaho-mqtt-dev, libjansson-dev, libminiupnpc-dev,
libconfig-dev, libpcap-dev, zlib1g-dev.

## Integration tests

Python-based integration tests live in `tests/integration/` and run via
Docker (see `.github/workflows/tests.yml`). These test full LinBPQ
instances.
