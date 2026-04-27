"""Phase 6 — two linbpq instances connected via AX/IP-over-UDP.

A and B each run their own linbpq.bin in their own tempdir, with an
AX/IP MAP entry pointing at the other and a static ROUTES: entry that
declares the peer as a NET/ROM neighbour with high quality.

Locking in:
- The two daemons can coexist (distinct dirs, distinct ports, no
  cross-talk on shared resources).
- NODES propagate from A to B over the AX/IP-UDP carrier — i.e. the
  end-to-end NET/ROM stack is wired through the BPQAXIP driver.
"""

from __future__ import annotations

import time
from contextlib import ExitStack
from string import Template

import pytest

from helpers.linbpq_instance import LinbpqInstance, PEER_CONFIG
from helpers.telnet_client import TelnetClient


def _peer_template(
    *,
    node_call: str,
    node_alias: str,
    peer_call: str,
    peer_axip_port: int,
) -> Template:
    """Return a Template that pre-substitutes the peer-related fields."""

    base = PEER_CONFIG.template

    class _T(Template):
        def substitute(self, **kw):
            return Template.substitute(
                self,
                node_call=node_call,
                node_alias=node_alias,
                peer_call=peer_call,
                peer_axip_port=peer_axip_port,
                **kw,
            )

    return _T(base)


@pytest.fixture
def two_instances(tmp_path):
    """Spin up two linbpq instances bidirectionally MAPped over AX/IP."""

    a_dir = tmp_path / "A"
    b_dir = tmp_path / "B"
    a_dir.mkdir()
    b_dir.mkdir()

    # Construct A and B with distinct identities.  Pre-allocate B's
    # AXIP port first so A's config can MAP it; then A's so B can MAP
    # back.  Building the LinbpqInstance picks the rest of the ports.
    a = LinbpqInstance(
        a_dir,
        config_template=_peer_template(
            node_call="N0AAA",
            node_alias="AAA",
            peer_call="N0BBB",
            peer_axip_port=0,  # rewritten below
        ),
    )
    b = LinbpqInstance(
        b_dir,
        config_template=_peer_template(
            node_call="N0BBB",
            node_alias="BBB",
            peer_call="N0AAA",
            peer_axip_port=a.axip_port,
        ),
    )
    # Now patch A's template with B's AXIP port.
    a.config_template = _peer_template(
        node_call="N0AAA",
        node_alias="AAA",
        peer_call="N0BBB",
        peer_axip_port=b.axip_port,
    )

    with ExitStack() as stack:
        stack.enter_context(a)
        stack.enter_context(b)
        yield a, b


def test_two_instances_coexist(two_instances):
    """Both instances start and remain reachable on telnet."""
    a, b = two_instances
    for inst, expected_call in ((a, b"N0AAA"), (b, b"N0BBB")):
        with TelnetClient("127.0.0.1", inst.telnet_port) as client:
            client.login("test", "test")
            response = client.run_command("PORTS")
        assert b"AXIP" in response, f"AXIP port missing on {expected_call!r}"


def test_routes_show_peer_neighbour(two_instances):
    """The static ROUTES: entry must register the peer as an L2
    neighbour visible in the ``ROUTES`` command output."""
    a, b = two_instances
    for inst, peer_call in ((a, b"N0BBB"), (b, b"N0AAA")):
        with TelnetClient("127.0.0.1", inst.telnet_port) as client:
            client.login("test", "test")
            response = client.run_command("ROUTES")
        assert peer_call in response, (
            f"{peer_call!r} not in ROUTES on the other side; "
            f"got: {response!r}"
        )


def test_downlink_connect_to_peer(two_instances):
    """``C 2 N0BBB`` (downlink-connect via the AX/IP port) reaches B,
    and a follow-up command runs against B's node session.

    Proves the L2/L4 stack rides correctly over the AX/IP-UDP carrier:
    A's CONNECT request arrives at B, B's link accepts, and traffic
    in both directions is interpreted by B's command parser.  Unlocks
    the Phase 3 deferral on connection commands.
    """
    a, b = two_instances
    # Port 2 is the AXIP port in both configs (Telnet is port 1).
    with TelnetClient("127.0.0.1", a.telnet_port, timeout=15) as client:
        client.login("test", "test")
        client.write_line("C 2 N0BBB")
        connect_response = client.read_until(b"Connected to N0BBB", timeout=10)
        assert b"Connected to N0BBB" in connect_response

        # Now we're cross-connected to B.  Send a command and assert
        # it's served by B (recognisable by B's prompt token).
        client.write_line("PORTS")
        peer_response = client.read_idle(idle_timeout=1.5, max_total=5.0)
    assert b"BBB:N0BBB}" in peer_response, (
        f"after connect we expected B's prompt token; got {peer_response!r}"
    )
    assert b"Ports" in peer_response, (
        f"PORTS via remote session didn't return list: {peer_response!r}"
    )


def test_connect_long_form_to_peer(two_instances):
    """Full-word ``CONNECT 2 N0BBB`` is accepted alongside the short ``C``."""
    a, _ = two_instances
    with TelnetClient("127.0.0.1", a.telnet_port, timeout=15) as client:
        client.login("test", "test")
        client.write_line("CONNECT 2 N0BBB")
        response = client.read_until(b"Connected to N0BBB", timeout=10)
    assert b"Connected to N0BBB" in response


def test_nc_alias_to_peer(two_instances):
    """``NC 2 N0BBB`` — alternative entry point for CONNECT — reaches B."""
    a, _ = two_instances
    with TelnetClient("127.0.0.1", a.telnet_port, timeout=15) as client:
        client.login("test", "test")
        client.write_line("NC 2 N0BBB")
        response = client.read_until(b"Connected to N0BBB", timeout=10)
    assert b"Connected to N0BBB" in response


def test_ctext_delivered_on_cross_instance_connect(tmp_path):
    """Configure ``CTEXT:`` on B; A connects to B over AX/IP-UDP
    and B's CTEXT body appears in A's session output.

    CTEXT (``L2Code.c:1382-1385``) only fires for L2 user connects to
    the node call/alias.  A NET/ROM-over-neighbour-link session
    bypasses it, so we deliberately omit the static ``ROUTES:``
    entry to make ``C 2 N0BBB`` stay at L2 raw-SABM rather than
    upgrading to a NET/ROM uplink via the neighbour."""
    from contextlib import ExitStack

    from helpers.linbpq_instance import LinbpqInstance, PEER_CONFIG

    a_dir = tmp_path / "A"
    b_dir = tmp_path / "B"
    a_dir.mkdir()
    b_dir.mkdir()

    # Strip ROUTES: from the base template, then inject CTEXT into B's
    # template only.
    no_routes = PEER_CONFIG.template
    routes_idx = no_routes.find("ROUTES:")
    if routes_idx != -1:
        no_routes = no_routes[:routes_idx]

    b_with_ctext = no_routes.replace(
        "LOCATOR=NONE\n",
        "LOCATOR=NONE\nCTEXT:\nWelcome to N0BBB test node!\n"
        "This is the connect text.\n***\n",
    )

    class _ATemplate(Template):
        def substitute(self, **kw):
            return Template.substitute(
                self,
                node_call="N0AAA", node_alias="AAA",
                peer_call="N0BBB", peer_axip_port=kw.pop("_pa", 0),
                **kw,
            )

    a = LinbpqInstance(a_dir, config_template=_ATemplate(no_routes))

    class _BTemplate(Template):
        def substitute(self, **kw):
            return Template.substitute(
                self,
                node_call="N0BBB", node_alias="BBB",
                peer_call="N0AAA", peer_axip_port=a.axip_port,
                **kw,
            )

    b = LinbpqInstance(b_dir, config_template=_BTemplate(b_with_ctext))

    class _ATemplate2(Template):
        def substitute(self, **kw):
            return Template.substitute(
                self,
                node_call="N0AAA", node_alias="AAA",
                peer_call="N0BBB", peer_axip_port=b.axip_port,
                **kw,
            )

    a.config_template = _ATemplate2(no_routes)

    with ExitStack() as stack:
        stack.enter_context(a)
        stack.enter_context(b)
        with TelnetClient("127.0.0.1", a.telnet_port, timeout=15) as client:
            client.login("test", "test")
            client.write_line("C 2 N0BBB")
            # CTEXT lands a beat after the Connected line; read until
            # the CTEXT body or until we time out.
            response = client.read_until(b"This is the connect text.", timeout=8)

    assert b"Connected to N0BBB" in response
    assert b"This is the connect text." in response, (
        f"CTEXT body not in cross-connect output: {response!r}"
    )


def test_nodes_propagation_and_l4_uplink_connect(two_instances):
    """End-to-end NODES propagation + L4-uplink connect form.

    Each instance has:
    - ``BROADCAST NODES`` in its BPQAXIP CONFIG block
    - ``B`` flag on the ``MAP`` entry pointing at the peer
    - PORT-block ``QUALITY=`` so SENDNODES doesn't skip the port
      (``L3Code.c:823`` filters out ``PORTQUALITY == 0`` ports)

    With those three plus the static ``ROUTES:`` neighbour entry,
    a sysop-triggered ``SENDNODES`` from each side propagates the
    peer's call into the other's NODES table, which is the
    pre-condition for L4-uplink ``C <call>`` (no port) to work.

    Tracks the resolution of
    [M0LTE/linbpq#4](https://github.com/M0LTE/linbpq/issues/4):
    L4-uplink between two instances over AX/IP-UDP.
    """
    a, b = two_instances

    # Trigger SENDNODES manually on both sides (sysop-only command).
    for inst in (a, b):
        with TelnetClient("127.0.0.1", inst.telnet_port, timeout=10) as client:
            client.login("test", "test")
            client.run_command("PASSWORD")
            client.run_command("SENDNODES")

    # Give both sides ~3s to receive each other's NODES broadcast and
    # update their tables (one fragment is enough for a single-peer
    # NODES list — no 10s inter-fragment delay needed).
    time.sleep(3)

    # Both NODES tables must list the peer call.
    for inst, peer_call in ((a, b"N0BBB"), (b, b"N0AAA")):
        with TelnetClient("127.0.0.1", inst.telnet_port, timeout=10) as client:
            client.login("test", "test")
            response = client.run_command("NODES")
        assert peer_call in response, (
            f"after SENDNODES, {peer_call!r} not in NODES on the other "
            f"instance — see issue #4. Got: {response!r}"
        )

    # And L4-uplink connect form (no port number) should now succeed.
    # The connect goes via NET/ROM uplink and emits two lines —
    # ``Trying ...`` (or similar) and ``Connected to N0BBB:BBB``.
    with TelnetClient("127.0.0.1", a.telnet_port, timeout=15) as client:
        client.login("test", "test")
        client.write_line("C N0BBB")
        connect_response = client.read_until(b"N0BBB", timeout=10)
        # Drain any trailing bits.
        connect_response += client.read_idle(idle_timeout=1.0, max_total=3.0)
    assert b"Connected" in connect_response, (
        f"L4-uplink C N0BBB should connect; got {connect_response!r}"
    )
    assert b"N0BBB" in connect_response, (
        f"L4-uplink connect response should reference N0BBB; "
        f"got {connect_response!r}"
    )


def test_nrr_finds_peer_after_nodes_propagation(two_instances):
    """``NRR <call>`` (NetRom Record Route) walks the NODES (DESTS)
    table for the call and emits a record-route packet (``Cmd.c:4231``).
    With an empty NODES table it returns ``Not found``; once #4's fix
    has propagated NODES, ``NRR N0BBB`` finds the entry and returns
    ``OK``."""
    a, b = two_instances

    # Trigger SENDNODES on both sides, wait for propagation.
    for inst in (a, b):
        with TelnetClient("127.0.0.1", inst.telnet_port, timeout=10) as client:
            client.login("test", "test")
            client.run_command("PASSWORD")
            client.run_command("SENDNODES")
    time.sleep(3)

    # Now NRR N0BBB on A should succeed (DESTS has N0BBB entry).
    # Response also includes the actual round-trip trace, e.g.
    # ``NRR Response in 2 Secs: N0AAA N0BBB* N0AAA``.
    with TelnetClient("127.0.0.1", a.telnet_port, timeout=10) as client:
        client.login("test", "test")
        response = client.run_command("NRR N0BBB", idle_timeout=3)
    assert b"Not found" not in response, (
        f"NRR after NODES propagation should find peer, got: {response!r}"
    )
    assert b"NRR Response" in response, (
        f"NRR should report a round-trip from N0BBB, got: {response!r}"
    )
    assert b"N0BBB" in response, (
        f"NRR Response trace should include N0BBB, got: {response!r}"
    )


def test_bye_from_peer_returns_to_local_node(two_instances):
    """After connecting to B, ``BYE`` drops the cross-link and returns
    the user to A's node prompt — verified by running a command and
    seeing A's prompt token, not B's."""
    a, _ = two_instances
    with TelnetClient("127.0.0.1", a.telnet_port, timeout=15) as client:
        client.login("test", "test")
        client.write_line("C 2 N0BBB")
        client.read_until(b"Connected to N0BBB", timeout=10)

        # Run a command on B to confirm we're cross-linked.
        client.write_line("INFO")
        peer_data = client.read_idle(idle_timeout=1.5, max_total=4.0)
        assert b"BBB:N0BBB}" in peer_data, (
            f"expected B's prompt before BYE, got {peer_data!r}"
        )

        # BYE the remote session.
        client.write_line("BYE")
        client.read_until(b"Disconnected", timeout=10)

        # Now run a command and assert it lands at A's prompt, not B's.
        client.write_line("PORTS")
        local_data = client.read_idle(idle_timeout=1.5, max_total=4.0)
    assert b"AAA:N0AAA}" in local_data, (
        f"after BYE expected A's prompt; got {local_data!r}"
    )
    assert b"BBB:N0BBB}" not in local_data, (
        f"still seeing B's prompt after BYE: {local_data!r}"
    )
