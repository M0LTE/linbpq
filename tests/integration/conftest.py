"""Shared pytest fixtures for the linbpq integration suite."""

from __future__ import annotations

from pathlib import Path

import pytest

from helpers.linbpq_instance import (
    CHAT_CONFIG,
    CHAT_CONFIG_FILE,
    IP_GATEWAY_CONFIG,
    LinbpqInstance,
    MAIL_CONFIG,
)


def pytest_collection_modifyitems(config, items):
    """Sort tests marked ``long_runtime`` to the front of the queue.

    pytest-xdist's default ``load`` scheduler hands tests out FIFO
    from the collected list.  Long-running timer-bound tests (e.g.
    waiting ~2min for an ID/BT beacon) should start first so they
    run in parallel with the rest of the suite — otherwise a worker
    might pick one up near the end and stretch overall wall-clock.
    """
    long_running = [i for i in items if i.get_closest_marker("long_runtime")]
    rest = [i for i in items if not i.get_closest_marker("long_runtime")]
    items[:] = long_running + rest


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


@pytest.fixture
def linbpq_mail(tmp_path: Path):
    """A linbpq with the BBS / mail subsystem enabled.

    Adds the ``mail`` command-line argument (which loads BPQMail) and
    uses ``MAIL_CONFIG`` so the BBS application alias is registered.
    """
    instance = LinbpqInstance(
        tmp_path,
        config_template=MAIL_CONFIG,
        extra_args=("mail",),
    )
    instance.start()
    try:
        yield instance
    finally:
        instance.stop()


@pytest.fixture
def linbpq_ipgw(tmp_path: Path):
    """A linbpq with the BPQ IP-gateway feature enabled.

    Uses ``IP_GATEWAY_CONFIG`` (adds a minimal IPGATEWAY ... ****
    block).  Enables the PING / ARP / NAT / IPROUTE / AXMHEARD /
    AXRESOLVER node commands.
    """
    instance = LinbpqInstance(
        tmp_path,
        config_template=IP_GATEWAY_CONFIG,
    )
    instance.start()
    try:
        yield instance
    finally:
        instance.stop()


@pytest.fixture
def linbpq_chat(tmp_path: Path):
    """A linbpq with the Chat subsystem enabled.

    Pre-writes ``chatconfig.cfg`` with ApplNum=1 (matching
    ``CHAT_CONFIG``'s slot-1 placement) so linbpq doesn't generate
    its own default with ApplNum=2 — which would land Chat on a slot
    we haven't allocated and trigger "Chat Init Failed".  Adds the
    ``chat`` command-line argument so linbpq actually starts Chat.
    """
    (tmp_path / "chatconfig.cfg").write_text(CHAT_CONFIG_FILE)
    instance = LinbpqInstance(
        tmp_path,
        config_template=CHAT_CONFIG,
        extra_args=("chat",),
    )
    instance.start()
    try:
        yield instance
    finally:
        instance.stop()
