# LinBPQ Fork — Development Guide

## Branch strategy

This fork uses two long-lived branches:

- **`master`** — clean mirror of upstream (John G8BPQ's official LinBPQ).
  Never commit local patches here. Only upstream syncs and docs/CI changes
  that don't touch LinBPQ source code.

- **`patched`** — our distribution branch. Carries local bug fixes rebased
  on top of master. Has its own releases (binary + Docker). Each patch is
  a single squashed commit with an `Upstream: PR #N, Issue #N` trailer.

### Rules

1. **Do not commit source fixes to master.** Propose them as PRs against
   master (so John can review), but land them on `patched` only.
2. **Each patch = one squashed commit.** Keep patches atomic and
   independent so they can be dropped individually.
3. **Order patches by severity:** critical first, then significant, then
   minor. This keeps the most important fixes closest to the base.

## Adding a new patch

```bash
git checkout patched
# Create a fix branch off master for the PR:
git checkout -b fix/description master
# ... make changes, write tests in tests/unit/, commit ...
git push -u origin fix/description
# Create PR against master (for upstream review)
# Then squash-merge onto patched:
git checkout patched
git merge --squash origin/fix/description
git commit  # with "Upstream: PR #N, Issue #N" trailer
# Update PATCHES.md
```

## Rebasing patched on master

When master advances (upstream sync or John merges a fix):

```bash
git checkout patched
git rebase master
# If a patch conflicts because upstream fixed the same thing:
#   git rebase --skip  (to drop the now-redundant patch)
# Update PATCHES.md — mark dropped patches as "superseded"
git push --force-with-lease origin patched
```

## Dropping a patch

When John merges an upstream fix that supersedes one of our patches:

1. Sync master: `git checkout master && git pull`
2. Rebase patched: `git checkout patched && git rebase master`
3. If the patch conflicts cleanly (same fix), skip it: `git rebase --skip`
4. If it partially conflicts, resolve and decide whether our version or
   John's is more complete.
5. Update PATCHES.md: change status from `pending` to `superseded`.
6. Force-push: `git push --force-with-lease origin patched`

## Releases and tagging

The `patched` branch has its own release tags and Docker images,
separate from upstream-clean releases.

### Tag scheme

- Upstream-clean: `v6.0.25.28` (matches `KVerstring` in `Versions.h`)
- Patched: `v6.0.25.28-patched.1` — the `.N` suffix increments with
  each new release of the patched branch against the same upstream version.
  When upstream advances, reset to `.1`.

### Cutting a release

```bash
git checkout patched
# Ensure all patches are rebased on current master
# Verify: make -C tests/unit test
git tag -a v6.0.25.28-patched.1 -m "Patched release: <summary>"
git push origin v6.0.25.28-patched.1
```

This triggers `docker-publish.yml` which publishes:
- `6.0.25.28-patched.1` (versioned tag)
- `patched-latest` (floating tag)

The `latest` Docker tag is NOT moved by patched releases — it tracks
upstream-clean `v*` tags only.

### CI

Both `master` and `patched` trigger the test suite on push. The test
workflow includes:
- **unit tests** — `make -C tests/unit test` (lightweight, no Docker)
- **integration (fast)** — pytest suite excluding long_runtime markers
- **integration (long_runtime)** — beacon/soak/leak tests
- **playwright** — browser-based UI tests

## Unit tests

Standalone C tests live in `tests/unit/`. They extract and test specific
logic without needing the full LinBPQ build. Run with:

```bash
make -C tests/unit test
```

Each patch should include a test that verifies the correct behaviour.
The Makefile auto-discovers `test_*.c` files via wildcard.

## Integration tests

Python-based integration tests live in `tests/integration/` and run via
Docker (see `.github/workflows/tests.yml`). These test full LinBPQ
instances.

## Building

```bash
make -j$(nproc)
```

Requires: libpaho-mqtt-dev, libjansson-dev, libminiupnpc-dev,
libconfig-dev, libpcap-dev, zlib1g-dev.
