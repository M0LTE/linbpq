"""Shared pytest fixtures for the linbpq integration suite."""

from __future__ import annotations

from pathlib import Path

import pytest

from helpers.linbpq_instance import LinbpqInstance


@pytest.fixture
def linbpq(tmp_path: Path):
    """A freshly-started linbpq.bin in a per-test temp directory.

    The instance is torn down (SIGTERM, then SIGKILL after 5s) at end of test.
    Stdout / stderr is captured to ``<tmp_path>/linbpq.stdout.log`` for
    post-mortem of failures.
    """
    instance = LinbpqInstance(tmp_path)
    instance.start()
    try:
        yield instance
    finally:
        instance.stop()
