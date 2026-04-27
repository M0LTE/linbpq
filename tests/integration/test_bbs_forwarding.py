"""Comprehensive coverage of BPQMail's FBB inter-BBS forwarding.

References:
- [FBB Forwarding Protocol spec](https://github.com/packethacking/ax25spec/blob/main/doc/fbb-forwarding-protocol.md)
- ``FBBRoutines.c`` (linbpq implementation)
- ``BBSUtilities.c`` ``CheckSID``, the BBS-side SID parser
- ``BPQMail.c`` ``SendFwdDetails`` (the ``FwdDetail.txt`` template
  enumerates every option exposed in the partner-config web screen)

Each test stands up linbpq with BPQMail enabled, pre-writes
``BPQMail.cfg`` with a forwarding-partner entry under
``BBSForwarding``, and a partner-BBS user under ``BBSUsers``
(flags=0x10 / ``F_BBS``).  A ``FBBPartner`` helper logs into the
BBS application and drives the protocol from the wire.
"""

from __future__ import annotations

import re
from pathlib import Path
from string import Template

import time

from helpers.bpqmail_cfg import FwdPartner, render_bpqmail_cfg
from helpers.fbb_partner import FBBPartner, fbb_partner
from helpers.linbpq_instance import LinbpqInstance
from helpers.telnet_client import TelnetClient


_FWD_NODE_CFG = Template(
    """\
SIMPLE=1
NODECALL=N0AAA
NODEALIAS=AAA
LOCATOR=NONE
APPLICATIONS=BBS
BBSCALL=N0AAA
BBSALIAS=BBS

PORT
 ID=Telnet
 DRIVER=Telnet
 CONFIG
 TCPPORT=$telnet_port
 HTTPPORT=$http_port
 MAXSESSIONS=10
 USER=test,test,N0SDR,,SYSOP
 USER=fbbuser,fbbpass,N0BBB,,
ENDPORT
"""
)


def _fwd_setup(
    work_dir: Path,
    partner_call: str = "N0BBB",
    **partner_overrides,
) -> LinbpqInstance:
    """Stand up a linbpq+BPQMail instance with one forwarding partner.

    Pre-writes ``BPQMail.cfg`` so the partner is recognised on boot.
    Caller should ``with`` the returned instance.
    """
    partner = FwdPartner(call=partner_call, **partner_overrides)
    cfg_text = render_bpqmail_cfg(
        bbs_call="N0AAA",
        sysop_call="N0AAA",
        hroute="GBR.EU",
        partners=[partner],
    )
    # On Linux, BPQMail's cfg is ``linmail.cfg`` (LinBPQ.c line 1136),
    # not the Windows ``BPQMail.cfg``.
    (work_dir / "linmail.cfg").write_text(cfg_text)

    return LinbpqInstance(
        work_dir,
        config_template=_FWD_NODE_CFG,
        extra_args=("mail",),
    )


def _fwd_setup_fbb_mode(work_dir: Path, **partner_overrides) -> LinbpqInstance:
    """Like ``_fwd_setup`` but with the cfg flags that linbpq needs to
    actually enter FBB-forwarding mode.

    FBB-mode kicks in only when ALL of these are set in the partner cfg:

    - ``allow_blocked`` (== ``F`` flag in SID)
    - ``allow_compressed`` (== ``B`` flag) — without it AND with a non-BPQ
      partner SID, linbpq downgrades to MBL (BBSUtilities.c:9351)

    Plus the partner must send a SID claiming compatible flags.
    Helper covers the typical case for tests that drive the full FBB
    proposal flow.
    """
    overrides = dict(
        allow_blocked=True,
        allow_compressed=True,
        allow_b1=True,
        allow_b2=True,
    )
    overrides.update(partner_overrides)
    return _fwd_setup(work_dir, **overrides)


# ----------------------------------------------------------------------
# SID exchange (FBB spec §2)
# ----------------------------------------------------------------------


def test_linbpq_bbs_sends_sid_with_required_F_flag(tmp_path: Path):
    """When a known partner BBS connects, linbpq sends a SID with the
    ``F`` capability flag.  Per FBB spec §2.2, ``F`` is required for
    any FBB-protocol operation; without it the partner falls back to
    MBL/RLI mode.

    Setting ``allow_blocked=True`` on the partner enables FBB mode in
    BPQMail's SID generator (BBSUtilities.c line 9094).
    """
    instance = _fwd_setup(tmp_path, allow_blocked=True)
    with instance as linbpq:
        with fbb_partner(
            "127.0.0.1",
            linbpq.telnet_port,
            username="fbbuser",
            password="fbbpass",
        ) as partner:
            sid = partner.login_to_bbs()

    sid_text = sid.decode("ascii", errors="replace")
    # Strip the leading [BPQ-X.Y.Z.A- and trailing $].
    flags_match = re.search(r"\[BPQ-[\d.]+-([^\]]+)\]", sid_text)
    assert flags_match, f"unexpected SID shape: {sid_text!r}"
    flags = flags_match.group(1)
    assert flags.endswith("$"), f"SID flags not $-terminated: {flags!r}"
    assert "F" in flags, (
        f"SID missing required F flag (FBB spec §2.2): {sid_text!r}"
    )


def test_sid_flag_matrix(tmp_path: Path):
    """The SID flags should reflect the partner's cfg settings:

    - ``allow_compressed`` → ``B``
    - ``allow_b2`` → ``2`` (BPQ omits ``1`` when B2 is also enabled —
      B2 implies B1, see ``BBSUtilities.c:9092``)
    - ``allow_blocked`` → ``F`` (FBB mode)

    Per spec §2.2 table.
    """
    instance = _fwd_setup(
        tmp_path,
        allow_blocked=True,
        allow_compressed=True,
        allow_b1=True,
        allow_b2=True,
    )
    with instance as linbpq:
        with fbb_partner(
            "127.0.0.1",
            linbpq.telnet_port,
            username="fbbuser",
            password="fbbpass",
        ) as partner:
            sid = partner.login_to_bbs()

    flags_match = re.search(rb"\[BPQ-[\d.]+-([^\]]+)\]", sid)
    assert flags_match, f"unexpected SID shape: {sid!r}"
    flags = flags_match.group(1)
    # B (compressed), 2 (B2 mode), F (FBB) all advertised; per spec
    # §2.2 every flag should be present until the $ end-marker.
    for c in (b"B", b"2", b"F"):
        assert c in flags, (
            f"SID flags {flags!r} missing capability {c!r}; want B2FW... per cfg"
        )


def test_sid_b1_only_advertises_1(tmp_path: Path):
    """``allow_b1=True, allow_b2=False`` advertises ``B1`` (the
    ``1`` flag) — locks in the alternative branch in the SID
    generator that selects ``1`` over ``2``."""
    instance = _fwd_setup(
        tmp_path,
        allow_blocked=True,
        allow_compressed=True,
        allow_b1=True,
        allow_b2=False,
    )
    with instance as linbpq:
        with fbb_partner(
            "127.0.0.1",
            linbpq.telnet_port,
            username="fbbuser",
            password="fbbpass",
        ) as partner:
            sid = partner.login_to_bbs()
    flags_match = re.search(rb"\[BPQ-[\d.]+-([^\]]+)\]", sid)
    assert flags_match, f"unexpected SID shape: {sid!r}"
    flags = flags_match.group(1)
    assert b"B" in flags and b"1" in flags and b"F" in flags, (
        f"B1 mode SID missing B/1/F: {flags!r}"
    )
    assert b"2" not in flags, (
        f"B1-only mode SID has 2 flag: {flags!r}"
    )


def test_sid_without_blocked_lacks_F_flag(tmp_path: Path):
    """If ``allow_blocked`` is OFF, BPQMail's SID lacks ``F`` and (per
    spec §2.3) the partner is expected to fall back to MBL/RLI mode.
    Locks in the cfg → SID-flag plumbing."""
    instance = _fwd_setup(tmp_path, allow_blocked=False)
    with instance as linbpq:
        with fbb_partner(
            "127.0.0.1",
            linbpq.telnet_port,
            username="fbbuser",
            password="fbbpass",
        ) as partner:
            sid = partner.login_to_bbs()

    flags_match = re.search(rb"\[BPQ-[\d.]+-([^\]]+)\]", sid)
    assert flags_match, f"unexpected SID shape: {sid!r}"
    flags = flags_match.group(1)
    assert b"F" not in flags, (
        f"SID has F flag despite allow_blocked=False: {flags!r}"
    )


# ----------------------------------------------------------------------
# Empty-queue protocol flow (FBB spec §4.1, §10.1)
# ----------------------------------------------------------------------


def _post_message(
    *,
    linbpq: LinbpqInstance,
    sender_user: str,
    sender_pass: str,
    to_call: str,
    at_call: str,
    msg_type: str = "P",
    title: str = "fwd-test-subject",
    body: str = "fwd-test-body",
    bbs_call: str = "N0AAA",
) -> bytes:
    """Use the SP / SB / ST sender command to post a message via telnet."""
    cmd = f"S{msg_type} {to_call} @ {at_call}"
    with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
        client.login(sender_user, sender_pass)
        # ``run_command("BBS")`` reads the BBS-app banner + prompt to idle.
        client.run_command("BBS", idle_timeout=1.5)
        client.write_line(cmd)
        client.read_until(b"Enter Title", timeout=5)
        client.write_line(title)
        client.read_until(b"Enter Message Text", timeout=5)
        client.write_line(body)
        time.sleep(0.5)
        client.write_line("/EX")
        return client.read_until(f"de {bbs_call}>".encode(), timeout=10)


def test_empty_queue_partner_initiated_session_ends_with_fq(tmp_path: Path):
    """Per FBB spec §4.1 / §10.1, the connecting (originating) station
    sends proposals first.  We connect in, send our SID, then send
    ``FF`` (no messages from us); linbpq with an empty outbound queue
    should respond ``FQ\\r`` to terminate the session.
    """
    instance = _fwd_setup_fbb_mode(tmp_path)
    with instance as linbpq:
        with fbb_partner(
            "127.0.0.1",
            linbpq.telnet_port,
            username="fbbuser",
            password="fbbpass",
        ) as partner:
            partner.login_to_bbs()
            partner.send_sid()
            partner.send_ff()
            line = partner.read_one_command(timeout=5)

    assert line.startswith(b"FQ"), (
        f"expected FQ after FF on empty queue (spec §10.1), got {line!r}"
    )


def test_partner_proposal_gets_fs_response(tmp_path: Path):
    """The partner sends a proposal block; linbpq responds ``FS <codes>``
    where each code is one of ``+`` / ``-`` / ``=`` (FBB spec §6.2).

    Per spec §5 (proposals) and §7.1 (ASCII transfer).
    """
    instance = _fwd_setup_fbb_mode(tmp_path)
    with instance as linbpq:
        with fbb_partner(
            "127.0.0.1",
            linbpq.telnet_port,
            username="fbbuser",
            password="fbbpass",
        ) as partner:
            partner.login_to_bbs()
            partner.send_sid()

            body = b"hello-from-partner\r"
            size = len(body)
            partner.send_proposal_block(
                [
                    f"FA P N0PEER N0AAA TESTUSER 12345_PEER {size}".encode()
                ]
            )
            fs = partner.read_one_command(timeout=5)

    assert fs.startswith(b"FS "), f"expected FS response, got {fs!r}"
    response_codes = fs[3:].rstrip(b"\r")
    assert len(response_codes) == 1, (
        f"FS response should have one code per proposal: {fs!r}"
    )
    assert response_codes[:1] in (b"+", b"-", b"=", b"Y", b"N", b"L"), (
        f"FS response code outside spec set (§6.2): {fs!r}"
    )


def test_multi_proposal_block_one_fs_code_per_proposal(tmp_path: Path):
    """Spec §5.3 / §6.1: up to 5 proposals per block; the FS line has
    exactly one response code per proposal."""
    instance = _fwd_setup_fbb_mode(tmp_path)
    with instance as linbpq:
        with fbb_partner(
            "127.0.0.1",
            linbpq.telnet_port,
            username="fbbuser",
            password="fbbpass",
        ) as partner:
            partner.login_to_bbs()
            partner.send_sid()
            # Send 3 distinct proposals.
            partner.send_proposal_block(
                [
                    b"FA P N0PEER N0AAA TESTUSER1 11111_PEER 10",
                    b"FA P N0PEER N0AAA TESTUSER2 22222_PEER 20",
                    b"FA P N0PEER N0AAA TESTUSER3 33333_PEER 30",
                ]
            )
            fs = partner.read_one_command(timeout=5)

    assert fs.startswith(b"FS "), f"expected FS response, got {fs!r}"
    codes = fs[3:].rstrip(b"\r")
    assert len(codes) == 3, (
        f"FS should have 3 codes for 3 proposals (spec §6.1), got {fs!r}"
    )


def test_proposal_with_oversized_call_rejected(tmp_path: Path):
    """FBB spec §5.1 / FBBRoutines.c:546: callsigns are max 6 chars.
    A proposal with a 7-char ``From`` field is rejected as a
    proposal-format error rather than treated as a normal reject."""
    instance = _fwd_setup_fbb_mode(tmp_path)
    with instance as linbpq:
        with fbb_partner(
            "127.0.0.1",
            linbpq.telnet_port,
            username="fbbuser",
            password="fbbpass",
        ) as partner:
            partner.login_to_bbs()
            partner.send_sid()
            # 7-char From — exceeds the max of 6.
            partner.send_proposal_block(
                [b"FA P TOOLONGX N0AAA TESTUSER 99999_PEER 5"]
            )
            line = partner.read_one_command(timeout=5)

    assert b"Protocol Error" in line or b"format error" in line, (
        f"oversized From field should trigger protocol error, got {line!r}"
    )


def test_protocol_error_on_non_F_command_after_sid(tmp_path: Path):
    """Per spec §4 / §5, all proposal-block commands start with ``F``;
    sending a non-F line after entering FBB mode should trigger
    ``*** Protocol Error - Line should start with 'F'`` (FBBRoutines.c:273)."""
    instance = _fwd_setup_fbb_mode(tmp_path)
    with instance as linbpq:
        with fbb_partner(
            "127.0.0.1",
            linbpq.telnet_port,
            username="fbbuser",
            password="fbbpass",
        ) as partner:
            partner.login_to_bbs()
            partner.send_sid()
            partner.send_line(b"GARBAGE COMMAND")
            line = partner.read_one_command(timeout=5)

    assert b"Protocol Error" in line, (
        f"non-F line should trigger protocol error, got {line!r}"
    )


def test_linbpq_sends_proposal_for_queued_message(tmp_path: Path):
    """End-to-end: queue a message for partner via SP, then have the
    partner connect and read its FBB proposal.

    Wire flow:
    1. local user SPs ``SP TESTUSER @ N0BBB`` — BPQMail's
       ``MatchMessagetoBBSList`` matches the @BBS to partner ``N0BBB``
       and sets ``fbbs[BBSNumber=1]`` on the message.
    2. Partner connects and exchanges SIDs.
    3. Partner sends ``FF`` (we have no messages to offer).
    4. linbpq's ``FBBDoForward`` finds the queued msg and sends an
       ``FA`` (compressed) proposal containing the right BID, From,
       To, ATBBS, and size.
    """
    instance = _fwd_setup_fbb_mode(tmp_path)
    with instance as linbpq:
        _post_message(
            linbpq=linbpq,
            sender_user="test",
            sender_pass="test",
            to_call="TESTUSER",
            at_call="N0BBB",
            msg_type="P",
            title="for-partner-subj",
            body="for-partner-body",
        )

        with fbb_partner(
            "127.0.0.1",
            linbpq.telnet_port,
            username="fbbuser",
            password="fbbpass",
        ) as partner:
            partner.login_to_bbs()
            partner.send_sid()
            partner.send_ff()
            # linbpq should now propose the queued message.
            proposals, terminator = partner.read_proposal_block(timeout=10)

    # FF/FQ-only "block" returned by helper means linbpq had nothing
    # to forward — that's a regression for this test.
    assert proposals and not proposals[0].startswith(b"F"[:2]) is False, (
        f"linbpq sent {proposals!r} {terminator!r} — expected an FA proposal"
    )
    assert any(p.startswith(b"FA") or p.startswith(b"FC") for p in proposals), (
        f"expected at least one FA/FC proposal, got {proposals!r}"
    )
    # FA carries To/From/AT inline; FC (B2) hides them inside the
    # encapsulated message and only carries BID + sizes (spec §11.2).
    proposal = proposals[0]
    if proposal.startswith(b"FA"):
        assert b"TESTUSER" in proposal, f"TO not in FA proposal: {proposal!r}"
        assert b"N0BBB" in proposal, f"ATBBS not in FA proposal: {proposal!r}"
    else:
        # FC BID format: ``<seq>_<bbs>`` (FBB spec §3.1).
        assert b"_N0AAA" in proposal, (
            f"FC proposal BID should reference originating BBS: {proposal!r}"
        )


def test_partner_accepts_proposal_and_receives_b2_framed_body(tmp_path: Path):
    """Full happy-path round-trip: partner accepts linbpq's B2 proposal
    and reads the SOH-framed message body.

    Per FBB spec §8.2, the body opens with ``\\x01`` (SOH) followed by
    a length byte; the field after the header begins with ``\\x02``
    (STX, data block).  We assert on the leading framing bytes and
    the title-in-header — the trailing EOT depends on exact compressed
    size and isn't worth chasing across LZHUF variants.
    """
    instance = _fwd_setup_fbb_mode(tmp_path)
    with instance as linbpq:
        _post_message(
            linbpq=linbpq,
            sender_user="test",
            sender_pass="test",
            to_call="TESTUSER",
            at_call="N0BBB",
            msg_type="P",
            title="round-trip-subj",
            body="round-trip-body" * 5,
        )

        with fbb_partner(
            "127.0.0.1",
            linbpq.telnet_port,
            username="fbbuser",
            password="fbbpass",
        ) as partner:
            partner.login_to_bbs()
            partner.send_sid()
            partner.send_ff()
            proposals, _ = partner.read_proposal_block(timeout=10)
            partner.send_fs_response(b"+")
            # Read the SOH header by hand — much simpler than driving
            # the full STX/EOT framing.
            soh = partner.read_bytes(1, timeout=10)
            length_b = partner.read_bytes(1, timeout=5)
            header = partner.read_bytes(length_b[0], timeout=5)
            stx = partner.read_bytes(1, timeout=5)

    assert soh == b"\x01", f"expected SOH, got 0x{soh[0]:02x}"
    assert b"round-trip-subj" in header, (
        f"title missing from B2 SOH-header: {header!r}"
    )
    assert b"\x00000000\x00" in header, (
        f"B2 header offset field malformed: {header!r}"
    )
    assert stx == b"\x02", (
        f"expected STX (start-of-data) after header, got 0x{stx[0]:02x}"
    )


def test_checksum_error_caught(tmp_path: Path):
    """Per FBB spec §5 / §6, ``F>`` carries an optional 2-digit hex
    checksum; if present and wrong, linbpq rejects the block.

    We send a proposal with a deliberately-wrong F> checksum.
    """
    instance = _fwd_setup_fbb_mode(tmp_path)
    with instance as linbpq:
        with fbb_partner(
            "127.0.0.1",
            linbpq.telnet_port,
            username="fbbuser",
            password="fbbpass",
        ) as partner:
            partner.login_to_bbs()
            partner.send_sid()
            partner.send_line(b"FA P N0PEER N0AAA TESTUSER 11111_PEER 5")
            partner.send_line(b"F> FF")  # bogus checksum
            line = partner.read_one_command(timeout=5)

    assert b"Checksum" in line or b"checksum" in line, (
        f"bad checksum should trigger checksum error, got {line!r}"
    )
