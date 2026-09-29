# LinBPQ Fork — Development Guide

## Branch strategy

- **`master`** - clean mirror of upstream (John G8BPQ's official LinBPQ).
  Never commit local patches here. Only upstream syncs and docs/CI changes
  that don't touch LinBPQ source code.

Source fixes are offered to John as PRs. There is no separate
distribution branch: the `patched` branch was retired on 2026-09-29 once
John had taken most of its fixes, and is archived as the tag
`archive/patched`.

## Releases

Each of John's releases is applied to master as one
`upstream: apply g8bpq/linbpq <version>` commit. Tagging master
`v<version>` (matching `KVerstring` in `Versions.h`) publishes the
`m0lte/linbpq:<version>` image, moves `latest`, and deploys the versioned
docs.

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
