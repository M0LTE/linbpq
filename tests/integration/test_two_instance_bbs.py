"""Phase 6 deeper — cross-instance BBS interaction over AX/IP-UDP.

Real-world packet-radio scenario: a user logs into node A via telnet,
downlink-connects to node B, enters B's BBS, and posts a message.
This exercises:

- AX/IP-UDP carrier (Phase 6 transport)
- NET/ROM downlink connect (Phase 3 deferral, Phase 6 unlocked)
- BPQMail SP / Title / Body / /EX flow (Phase 4) on a *remote* BBS
- BPQMail's persistence — the message file on disk on B's side

We post and verify on B's filesystem that the message landed.  We
do *not* try to read the message back via a second telnet session
on B: BPQMail's read-authz checks the recipient call against the
caller's call (and rejects with "Message N not for you" otherwise).
A meaningful read-back test needs a configured BBS user with
appropriate privileges, which is its own batch.
"""

from __future__ import annotations

import time
from contextlib import ExitStack
from pathlib import Path
from string import Template

import pytest

from helpers.linbpq_instance import LinbpqInstance, PEER_MAIL_CONFIG
from helpers.telnet_client import TelnetClient


def _peer_mail_template(
    *,
    node_call: str,
    node_alias: str,
    bbs_call: str,
    peer_call: str,
    peer_axip_port: int,
) -> Template:
    base = PEER_MAIL_CONFIG.template

    class _T(Template):
        def substitute(self, **kw):
            return Template.substitute(
                self,
                node_call=node_call,
                node_alias=node_alias,
                bbs_call=bbs_call,
                peer_call=peer_call,
                peer_axip_port=peer_axip_port,
                **kw,
            )

    return _T(base)


@pytest.fixture
def two_mail_instances(tmp_path: Path):
    """Two BBS-enabled linbpq instances bidirectionally MAPped over AX/IP."""
    a_dir = tmp_path / "A"
    b_dir = tmp_path / "B"
    a_dir.mkdir()
    b_dir.mkdir()

    a = LinbpqInstance(
        a_dir,
        config_template=_peer_mail_template(
            node_call="N0AAA",
            node_alias="AAA",
            bbs_call="N0AAA-1",
            peer_call="N0BBB",
            peer_axip_port=0,  # patched after b is constructed
        ),
        extra_args=("mail",),
    )
    b = LinbpqInstance(
        b_dir,
        config_template=_peer_mail_template(
            node_call="N0BBB",
            node_alias="BBB",
            bbs_call="N0BBB-1",
            peer_call="N0AAA",
            peer_axip_port=a.axip_port,
        ),
        extra_args=("mail",),
    )
    a.config_template = _peer_mail_template(
        node_call="N0AAA",
        node_alias="AAA",
        bbs_call="N0AAA-1",
        peer_call="N0BBB",
        peer_axip_port=b.axip_port,
    )

    with ExitStack() as stack:
        stack.enter_context(a)
        stack.enter_context(b)
        yield a, b


def test_cross_instance_bbs_post_persists_on_remote(two_mail_instances):
    """Post a message via A's session into B's BBS (via downlink-connect
    over AX/IP), and verify the message lands in B's mail store on disk."""
    a, b = two_mail_instances

    with TelnetClient("127.0.0.1", a.telnet_port, timeout=15) as client:
        client.login("test", "test")
        client.write_line("C 2 N0BBB")
        client.read_until(b"Connected to N0BBB", timeout=10)

        # We're at B's node prompt now; enter B's BBS application.
        client.write_line("BBS")
        client.read_until(b"Please enter your Name", timeout=8)
        client.read_until(b">", timeout=5)
        client.write_line("RemoteTester")
        client.read_until(b"de N0BBB>", timeout=8)

        client.write_line("SP N0BBB")
        client.read_until(b"Enter Title", timeout=5)
        client.write_line("cross-instance-subject")
        client.read_until(b"Enter Message Text", timeout=5)
        client.write_line("cross-instance-body")
        time.sleep(0.5)
        client.write_line("/EX")
        save_response = client.read_until(b"Bid:", timeout=10)

    # The "Message: <N> Bid:" line confirms BPQMail accepted the post.
    assert b"Message:" in save_response and b"Bid:" in save_response, (
        f"no save confirmation: {save_response!r}"
    )

    # And the message body lives on B's disk under Mail/m_*.mes
    # (BPQMail stores the body inline in the .mes file; titles and
    # the rest of the message header live elsewhere in the message
    # database — out of scope for this test).
    mail_dir = b.work_dir / "Mail"
    assert mail_dir.is_dir(), f"no Mail dir on B: {b.work_dir}"

    found_body = False
    for mes in mail_dir.glob("m_*.mes"):
        if b"cross-instance-body" in mes.read_bytes():
            found_body = True
            break
    assert found_body, (
        f"body not found in any .mes file under {mail_dir}; "
        f"files: {[p.name for p in mail_dir.glob('m_*.mes')]}"
    )
