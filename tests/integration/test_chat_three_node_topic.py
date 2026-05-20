"""Regression: chat topic propagation across a three-node chain.

Topology: A <-> B <-> C, all linked over AX/IP-UDP, all running the
chat application.

Bug: ``HanksRT.c:topic_xmit`` used to identify each user's home node
as ``OurNode`` (the node sending the state-dump) rather than
``user->node->call``.  That mismatched the join record emitted by
``user_xmit`` immediately before, so receivers looking the user up
via ``user_find(call, node)`` silently dropped the topic update.
On the far node the user ended up listed in topic "General"
instead of the topic they had actually joined.

The path is only exercised when chat links *come up* — once links
are established, ``echo()`` relays the original buffer verbatim and
the home-node call is preserved.  The test starts all three nodes
with no chat traffic in flight, then has a user join on A and
select a topic, which lazily brings up A->B and then B->C — and so
each receiver sees the user appear via a fresh ``state_tell``.
"""

from __future__ import annotations

import time
from contextlib import ExitStack
from pathlib import Path
from string import Template

import pytest

from helpers.linbpq_instance import LinbpqInstance, pick_free_port
from helpers.telnet_client import TelnetClient


# Per-node bpq32.cfg.  Each node:
#
# * Declares chat as a NET/ROM application with an explicit
#   ``APPLICATION`` line — that's what gets the chat callsign
#   (``$chat_call``) into the NODES table, so peers can ``C <call>``
#   it once SENDNODES has propagated.  ``APPL1CALL`` alone (without
#   an ``APPLICATION`` line carrying a quality) won't put the chat
#   callsign on the wire.
# * Has an AXIP port with one or more ``MAP`` lines, ``BROADCAST
#   NODES``, ``QUALITY=200`` so SENDNODES doesn't skip it.
# * Carries static ``ROUTES:`` neighbour entries for each peer so
#   NET/ROM has a neighbour to chase the SENDNODES out of.
NODE_TEMPLATE = Template(
    """\
SIMPLE=1
NODECALL=$node_call
NODEALIAS=$node_alias
LOCATOR=NONE
APPLICATION 1,CHAT,,$chat_call,$chat_alias,255

PORT
 ID=Telnet
 DRIVER=Telnet
 CONFIG
 TCPPORT=$telnet_port
 HTTPPORT=$http_port
 NETROMPORT=$netrom_port
 FBBPORT=$fbb_port
 APIPORT=$api_port
 MAXSESSIONS=10
 USER=test,test,$node_call,,SYSOP
ENDPORT

PORT
 ID=AXIP
 DRIVER=BPQAXIP
 QUALITY=200
 MINQUAL=1
 CONFIG
 UDP $axip_port
 BROADCAST NODES
$map_lines
ENDPORT

ROUTES:
$routes_lines
***
"""
)


def _chatconfig(other_nodes: str) -> str:
    """Build chatconfig.cfg with the configured ``OtherChatNodes``."""
    return (
        "Chat :\n"
        "{\n"
        "  ApplNum = 1;\n"
        "  MaxStreams = 10;\n"
        "  reportChatEvents = 0;\n"
        "  chatPaclen = 236;\n"
        f'  OtherChatNodes = "{other_nodes}";\n'
        '  ChatWelcomeMsg = "Welcome";\n'
        '  MapPosition = "";\n'
        '  MapPopup = "";\n'
        "  PopupMode = 0;\n"
        "};\n"
    )


def _build_node(
    work_dir: Path,
    *,
    node_call: str,
    node_alias: str,
    chat_call: str,
    chat_alias: str,
    peers: list[tuple[str, int]],
    other_chat_nodes: str,
) -> LinbpqInstance:
    """Allocate ports, write chatconfig.cfg, return a configured instance.

    ``peers`` is a list of (peer_node_call, peer_axip_port).
    """
    work_dir.mkdir(parents=True, exist_ok=True)

    map_lines = "\n".join(
        f" MAP {peer_call} 127.0.0.1 UDP {peer_port} B"
        for peer_call, peer_port in peers
    )
    routes_lines = "\n".join(f"{peer_call},200,2" for peer_call, _ in peers)

    class _T(Template):
        def substitute(self, **kw):
            return Template.substitute(
                self,
                node_call=node_call,
                node_alias=node_alias,
                chat_call=chat_call,
                chat_alias=chat_alias,
                map_lines=map_lines,
                routes_lines=routes_lines,
                **kw,
            )

    inst = LinbpqInstance(
        work_dir,
        config_template=_T(NODE_TEMPLATE.template),
        extra_args=("chat",),
    )
    (work_dir / "chatconfig.cfg").write_text(_chatconfig(other_chat_nodes))
    return inst


def _enter_chat(client: TelnetClient, name: str) -> bytes:
    """Authenticate, enter CHAT, register a name; return the welcome block."""
    client.login("test", "test")
    client.write_line("CHAT")
    client.read_until(b"Please enter your Name", timeout=5)
    client.read_until(b">", timeout=5)
    client.write_line(name)
    return client.read_idle(idle_timeout=1.0, max_total=4.0)


def _set_qth(client: TelnetClient, qth: str) -> None:
    """``/Q <qth>`` — set an ASCII QTH.

    The default QTH used by the chat server contains a non-ASCII
    separator placeholder which the receiver's chat-link corruption
    check refuses.  An explicit ASCII ``/Q`` value avoids that path
    so the user record actually propagates, and the regression we
    care about (topic mismatch in state_tell) becomes observable.
    """
    client.write_line(f"/Q {qth}")
    client.read_idle(idle_timeout=0.5, max_total=2.0)


@pytest.fixture
def chat_chain(tmp_path: Path):
    """Spin up three chat-enabled linbpq instances chained A<->B<->C."""

    # Allocate AXIP ports up front so each side's MAP line can name
    # the peer.  LinbpqInstance picks an axip_port in __init__; we
    # pre-allocate and override.
    a_axip = pick_free_port()
    b_axip = pick_free_port()
    c_axip = pick_free_port()

    a = _build_node(
        tmp_path / "A",
        node_call="N0AAA",
        node_alias="AAA",
        chat_call="N0AAA-1",
        chat_alias="CHATA",
        peers=[("N0BBB", b_axip)],
        # ALIAS:CALL form.  Alias before the colon is just a label;
        # the connect script is "C CALL" so CALL needs to be in
        # NODES — that's what the APPLICATION line above gives us.
        other_chat_nodes="CHATB:N0BBB-1",
    )
    a.axip_port = a_axip

    b = _build_node(
        tmp_path / "B",
        node_call="N0BBB",
        node_alias="BBB",
        chat_call="N0BBB-1",
        chat_alias="CHATB",
        peers=[("N0AAA", a_axip), ("N0CCC", c_axip)],
        other_chat_nodes="CHATA:N0AAA-1, CHATC:N0CCC-1",
    )
    b.axip_port = b_axip

    c = _build_node(
        tmp_path / "C",
        node_call="N0CCC",
        node_alias="CCC",
        chat_call="N0CCC-1",
        chat_alias="CHATC",
        peers=[("N0BBB", b_axip)],
        other_chat_nodes="CHATB:N0BBB-1",
    )
    c.axip_port = c_axip

    with ExitStack() as stack:
        stack.enter_context(a)
        stack.enter_context(b)
        stack.enter_context(c)

        # Drive NODES propagation so A learns C's chat callsign (via
        # B) and vice versa.  Two rounds: first advertises the local
        # node, second carries the freshly-learned remote node
        # forward — enough for a 3-hop chain.
        for _ in range(2):
            for inst in (a, b, c):
                with TelnetClient("127.0.0.1", inst.telnet_port) as client:
                    client.login("test", "test")
                    client.run_command("PASSWORD")
                    client.run_command("SENDNODES")
            time.sleep(2)

        yield a, b, c


def test_topic_propagates_across_three_node_chain(chat_chain):
    """A user joining a topic on A appears in the same topic on C.

    Pre-fix, B->C state_tell stamped the topic record with B's
    OurNode while A had been announced as the user's home node, so
    C dropped the topic update on lookup and the user showed up
    on C in topic "General".
    """
    a, _b, c = chat_chain

    with ExitStack() as stack:
        # 1. Alice joins chat on A, sets a clean ASCII QTH, then
        #    switches topic.
        a_client = stack.enter_context(
            TelnetClient("127.0.0.1", a.telnet_port, timeout=15)
        )
        _enter_chat(a_client, "Alice")
        _set_qth(a_client, "Cardross")
        a_client.write_line("/T DMRPKT")
        a_client.read_idle(idle_timeout=1.0, max_total=3.0)

        # 2. Let A->B and B->C chat links come up lazily.  Connect
        #    setup over loopback is fast but ``makelinks`` polls on
        #    a 10-second cadence; allow some headroom.
        time.sleep(15)

        # 3. Sysop session at C inspects the user list.
        c_client = stack.enter_context(
            TelnetClient("127.0.0.1", c.telnet_port, timeout=15)
        )
        _enter_chat(c_client, "Carol")
        _set_qth(c_client, "Glasgow")
        # Drain any pending banner output, then /U.
        c_client.read_idle(idle_timeout=0.5, max_total=1.5)
        c_client.write_line("/U")
        users = c_client.read_idle(idle_timeout=1.5, max_total=5.0)

    # The remote user must be present.  ``show_users`` prints
    # ``<call> at <alias> <name>, <qth> [<topic>] Idle ...``.
    assert b"Alice" in users, (
        f"Alice@A not visible on C — chat links may not have come up. "
        f"got: {users!r}"
    )

    # The actual regression assertion: Alice must be in DMRPKT,
    # not the default "General".
    alice_line = next(
        (line for line in users.split(b"\r") if b"Alice" in line),
        None,
    )
    assert alice_line is not None, f"no Alice line in /U: {users!r}"
    assert b"[DMRPKT]" in alice_line, (
        f"Alice should be in topic DMRPKT on C (would show "
        f"[General] without the topic_xmit fix); got: {alice_line!r}"
    )
