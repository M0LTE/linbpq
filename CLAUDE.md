# LinBPQ Fork — Development Guide

## Branch strategy

- **`master`** - John G8BPQ's official LinBPQ plus a small number of
  fork fixes. It is the only long-lived branch.

Fork fixes land on master when they're worth carrying before John
releases them (for example #71, the KISS-over-TCP start-up crash). Offer
each one to John as well, and drop it when one of his releases includes
it. Keep each fix to a single commit so it's easy to find and drop.

The `patched` branch used to carry fixes separately. It was retired on
2026-09-29 once John had taken most of them, and is archived as the tag
`archive/patched`.

## Releases

Each of John's releases is applied to master as one
`upstream: apply g8bpq/linbpq <version>` commit. Tagging master
`v<version>` (matching `KVerstring` in `Versions.h`) publishes the
`m0lte/linbpq:<version>` image, moves `latest`, and deploys the versioned
docs. The image is built from master, so it includes any fork fixes
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
