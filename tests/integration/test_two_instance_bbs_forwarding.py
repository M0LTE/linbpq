"""Two real BPQMail daemons forwarding to each other over AX/IP-UDP.

Sister to ``test_bbs_forwarding.py`` (which exercises the FBB
protocol against a Python-side fake-FBB-partner), this test runs
two real linbpq+BPQMail daemons in their own work dirs, connected
over BPQAXIP-over-UDP, with a forwarding-partner cfg on each side
that points at the other.

What this exercises that the fake-partner tests don't:

- BPQMail's *outbound* dialler — the periodic ``ConnectScript``
  driven by ``StartForwarding`` (BBSUtilities.c:7752) actually
  reaches a remote BPQMail via the local node's L2 stack.
- The connect-script processor's prompt matching against another
  linbpq's real responses (``CONNECTED``, FBB SID, etc.).
- A round-trip through the AX/IP-UDP transport with a real
  inbound connection landing on the partner BBS application.

The fake-FBB-partner harness in ``test_bbs_forwarding.py`` is kept
alongside; it remains the right tool for fine-grained protocol
behaviour (per-flag SID variants, spec-violation handling, mode
fallbacks etc.) and for any work that wants a controlled FBB peer
without a second real BPQMail.

Plan estimates this test at 200–400 LoC; this file lands at the
lower end by reusing ``helpers/bpqmail_cfg.py`` and
``helpers/linbpq_instance.PEER_MAIL_CONFIG``.
"""

from __future__ import annotations

import time
from contextlib import ExitStack
from pathlib import Path
from string import Template

import pytest

from helpers.bpqmail_cfg import FwdPartner, render_bpqmail_cfg
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
    """Bind the ``PEER_MAIL_CONFIG`` substitutions for one side."""
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


def _write_linmail(
    work_dir: Path,
    *,
    bbs_call: str,
    sysop_call: str,
    partner_call: str,
    connect_script: list[str],
    fwd_interval: int,
) -> None:
    """Pre-write ``linmail.cfg`` so BPQMail recognises the partner
    on boot.  Both sides have a ``BBSForwarding`` entry — A actually
    dials, B is set up to answer (and could dial back if it had
    queued traffic, but we don't test reverse here)."""
    partner = FwdPartner(
        call=partner_call,
        connect_script=connect_script,
        fwd_interval=fwd_interval,
        # Required for FBB-mode SID exchange — without these the
        # partner downgrades to MBL (BBSUtilities.c:9351).
        allow_blocked=True,
        allow_compressed=True,
        allow_b1=True,
        allow_b2=True,
        # Forwarding-driven test: send messages immediately, no
        # batching delay beyond ``fwd_interval``.
        send_new_immediately=True,
    )
    cfg_text = render_bpqmail_cfg(
        bbs_call=bbs_call,
        sysop_call=sysop_call,
        partners=[partner],
    )
    (work_dir / "linmail.cfg").write_text(cfg_text)


@pytest.fixture
def two_mail_instances_for_forwarding(tmp_path: Path):
    """Two BBS-enabled daemons MAPped over AX/IP-UDP, each with a
    forwarding-partner cfg pointing at the other.

    A's ``ConnectScript`` dials B (via the AXIP carrier on port 2);
    B's is symmetric but won't fire unless we queue a message for A.
    """
    a_dir = tmp_path / "A"
    b_dir = tmp_path / "B"
    a_dir.mkdir()
    b_dir.mkdir()

    # First construct both LinbpqInstance objects to lock in axip ports,
    # then re-bind A's config_template once we know B's port.  Same
    # dance as the existing two_mail_instances fixture.
    a = LinbpqInstance(
        a_dir,
        config_template=_peer_mail_template(
            node_call="N0AAA",
            node_alias="AAA",
            bbs_call="N0AAA-1",
            peer_call="N0BBB",
            peer_axip_port=0,
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

    # Pre-write each side's BPQMail cfg.  ``ConnectScript`` on A
    # dials port 2 (AXIP) to B's BBS application call; B has the
    # symmetric entry but no script in the test (won't dial back).
    #
    # Partner call MUST match the SOURCE call seen on the inbound
    # connect.  When A's BBS dials out, the source AX.25 call is
    # A's ``BBSCALL`` (``N0AAA-1``).  So B needs a BBSUsers entry
    # for ``N0AAA-1`` with the F_BBS flag — otherwise B treats the
    # inbound as a regular user, no FBB SID exchange happens, and
    # nothing forwards.  Symmetric on the A side.
    # ConnectScript dials B's NODE call (N0BBB) on port 2 (AXIP) —
    # this is the connect form that ``test_two_instance.py`` already
    # proves works.  Once at B's node prompt, the second line ``BBS``
    # enters B's BBS application; the BBS app announces its SID
    # and the FBB exchange begins.
    _write_linmail(
        a_dir,
        bbs_call="N0AAA-1",
        sysop_call="N0AAA",
        partner_call="N0BBB-1",
        connect_script=["C 2 N0BBB", "BBS"],
        fwd_interval=2,
    )
    _write_linmail(
        b_dir,
        bbs_call="N0BBB-1",
        sysop_call="N0BBB",
        partner_call="N0AAA-1",
        connect_script=[],  # don't dial back
        fwd_interval=3600,
    )

    with ExitStack() as stack:
        stack.enter_context(a)
        stack.enter_context(b)
        # Give NODES a moment to propagate so ``C 2 N0BBB-1`` resolves.
        time.sleep(2.0)
        yield a, b


def _post_personal_msg_to_remote_user(
    linbpq: LinbpqInstance, *, to_user: str, at_call: str, body: str
) -> None:
    """Log into A's BBS as a regular user and post a P message
    addressed to ``to_user @ at_call``.  Returns once BPQMail
    confirms the save with the ``Bid:`` line.

    Mirrors ``test_bbs_forwarding.py::_post_message``: with our
    pre-written ``linmail.cfg`` setting ``DontNeedName=1``,
    BPQMail skips the new-user-name prompt and goes straight to
    the BBS prompt — so we idle past the banner with
    ``run_command("BBS", idle_timeout=...)`` rather than expecting
    the prompt explicitly.
    """
    with TelnetClient("127.0.0.1", linbpq.telnet_port, timeout=15) as client:
        client.login("test", "test")
        client.run_command("BBS", idle_timeout=1.5)
        client.write_line(f"SP {to_user} @ {at_call}")
        client.read_until(b"Enter Title", timeout=5)
        client.write_line("forwarded-subject")
        client.read_until(b"Enter Message Text", timeout=5)
        client.write_line(body)
        time.sleep(0.3)
        client.write_line("/EX")
        save = client.read_until(b"Bid:", timeout=10)

    assert b"Message:" in save and b"Bid:" in save, (
        f"BPQMail didn't accept the post: {save!r}"
    )


def _wait_for_message_on_remote(
    work_dir: Path, body: str, timeout: float = 60.0
) -> bool:
    """Poll the remote BBS's Mail/ dir until any ``m_*.mes`` file
    contains ``body`` (the message has been forwarded), or the
    deadline passes."""
    body_bytes = body.encode("ascii")
    mail_dir = work_dir / "Mail"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if mail_dir.is_dir():
            for mes in mail_dir.glob("m_*.mes"):
                try:
                    if body_bytes in mes.read_bytes():
                        return True
                except OSError:
                    pass
        time.sleep(0.5)
    return False


def test_two_real_bpqmail_daemons_forward_personal_message(
    two_mail_instances_for_forwarding,
):
    """A user posts a personal message on A addressed to a user
    @ N0BBB.  A's BPQMail forwarding scheduler (FwdInterval=2)
    fires within seconds, ConnectScript dials B's BBS application
    over AX/IP-UDP, FBB SID exchange + B2 transfer completes, and
    the message body lands on B's disk under ``Mail/m_*.mes``.

    Total wall-clock: 2-3s for NODES propagation + ≤2s for
    forwarding fire + a few seconds for the FBB exchange + disk
    flush.  Allow a generous 60s for slow CI.
    """
    a, b = two_mail_instances_for_forwarding

    body = "two-real-bpqmail-fwd-body-0xCAFE"
    # Use the SSID-1 form for ``@`` so it matches our partner BBSUsers
    # key exactly — BPQMail's partner-lookup is a case-insensitive
    # exact match including SSID.
    _post_personal_msg_to_remote_user(
        a, to_user="USERX", at_call="N0BBB-1", body=body
    )

    arrived = _wait_for_message_on_remote(b.work_dir, body, timeout=180.0)
    assert arrived, (
        f"message body {body!r} not found in B's Mail/m_*.mes within 180s; "
        f"A bbs log tail: "
        f"{next(iter((a.work_dir / 'logs').glob('log_*_BBS.txt')), None)}; "
        f"B bbs log tail: "
        f"{next(iter((b.work_dir / 'logs').glob('log_*_BBS.txt')), None)}"
    )
