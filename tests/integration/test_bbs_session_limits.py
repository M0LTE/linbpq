"""Fork additions to BBS partner session control.

- ``INTERLOCK <port>`` in any partner's connect script now also refuses
  incoming partner connects on that port while another BBS session is
  on it (``IsNamedInInterlock`` / ``Connected`` in BBSUtilities.c).
- ``INTERLOCK GROUP <n>`` does the same across every port with
  ``INTERLOCK=<n>`` in bpq32.cfg.  Two Telnet ports stand in for two
  HF ports sharing a radio.
- ``MaxSessionTime`` / ``SessionLockout`` (minutes, per partner) cut a
  partner session off after the limit, then refuse sessions with that
  partner in both directions until the lockout ends.  Checked from
  ``BBSSlowTimer``, which runs every 10 seconds.

Partners connect over the Telnet driver, which is port 1, so
``INTERLOCK 1`` covers them.  A refused partner never gets the SID and
``de N0AAA>`` prompt, which is what these tests look for.  The BBS log
is buffered for up to 30s, so it's mostly only used for failure
messages.
"""

from __future__ import annotations

import re
import socket
import time
import zlib
from pathlib import Path
from string import Template

import pytest

from helpers.bpqmail_cfg import FwdPartner, render_bpqmail_cfg
from helpers.fbb_partner import fbb_partner
from helpers.linbpq_instance import LinbpqInstance, pick_free_port


_NODE_CFG = Template(
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
 USER=bbbuser,bbbpass,N0BBB,,
 USER=cccuser,cccpass,N0CCC,,
 USER=ddduser,dddpass,N0DDD,,
ENDPORT
"""
)

_LOGINS = {
    "N0BBB": ("bbbuser", "bbbpass"),
    "N0CCC": ("cccuser", "cccpass"),
    "N0DDD": ("ddduser", "dddpass"),
}


_TWO_PORT_CFG = """\
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
 INTERLOCK={group1}
 CONFIG
 TCPPORT=$telnet_port
 HTTPPORT=$http_port
 MAXSESSIONS=10
 USER=test,test,N0SDR,,SYSOP
 USER=bbbuser,bbbpass,N0BBB,,
 USER=cccuser,cccpass,N0CCC,,
 USER=ddduser,dddpass,N0DDD,,
ENDPORT

PORT
 ID=Telnet2
 DRIVER=Telnet
 INTERLOCK={group2}
 CONFIG
 TCPPORT={telnet2_port}
 MAXSESSIONS=10
 USER=bbbuser,bbbpass,N0BBB,,
 USER=cccuser,cccpass,N0CCC,,
 USER=ddduser,dddpass,N0DDD,,
ENDPORT
"""


def _setup(
    work_dir: Path,
    partners: list[FwdPartner],
    config_template: Template = _NODE_CFG,
) -> LinbpqInstance:
    (work_dir / "linmail.cfg").write_text(
        render_bpqmail_cfg(
            bbs_call="N0AAA",
            sysop_call="N0AAA",
            hroute="GBR.EU",
            partners=partners,
        )
    )
    return LinbpqInstance(
        work_dir, config_template=config_template, extra_args=("mail",)
    )


def _setup_two_ports(
    work_dir: Path, partners: list[FwdPartner], group1: int, group2: int
) -> tuple[LinbpqInstance, int]:
    """Two Telnet ports (1 and 2) with the given INTERLOCK= groups.

    Returns the instance and the second port's TCP port.
    """
    telnet2_port = pick_free_port()
    template = Template(
        _TWO_PORT_CFG.format(
            group1=group1, group2=group2, telnet2_port=telnet2_port
        )
    )
    return _setup(work_dir, partners, template), telnet2_port


def _partner(call: str, **overrides) -> FwdPartner:
    # Disabled, so linbpq never dials out and the only sessions are
    # the ones each test makes.  ConTimeout is long so the SID
    # timeout doesn't end a session before MaxSessionTime does.
    overrides.setdefault("enabled", False)
    overrides.setdefault("con_timeout", 600)
    return FwdPartner(call=call, **overrides)


def _connect(linbpq: LinbpqInstance, call: str, tcp_port: int | None = None):
    username, password = _LOGINS[call]
    return fbb_partner(
        "127.0.0.1",
        tcp_port or linbpq.telnet_port,
        username=username,
        password=password,
    )


def _accepted(partner) -> bool:
    """Log in and enter the BBS.  True if we got the SID and prompt."""
    try:
        partner.login_to_bbs()
        return True
    except (TimeoutError, ConnectionResetError, RuntimeError):
        return False


def _bbs_log(work_dir: Path) -> str:
    return "".join(
        p.read_text(errors="replace")
        for p in sorted((work_dir / "logs").glob("log_*_BBS.txt"))
    )


def _wait_for_cutoff(partner, timeout: float) -> float | None:
    """Wait for linbpq to send anything, or close, on an idle session.

    Returns seconds waited, or None if nothing happened in ``timeout``.
    """
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        try:
            if partner._read_more(max_seconds=1.0):
                return time.monotonic() - start
        except (ConnectionResetError, OSError):
            return time.monotonic() - start
    return None


# ----------------------------------------------------------------------
# Incoming interlock
# ----------------------------------------------------------------------


def test_interlock_refuses_second_incoming_partner(tmp_path: Path):
    """With ``INTERLOCK 1`` in a partner's script, a second partner
    connecting in on port 1 is refused while the first is connected,
    and accepted once the first has gone."""
    instance = _setup(
        tmp_path,
        [
            _partner("N0BBB", connect_script=["INTERLOCK 1", "C N0BBB"]),
            _partner("N0CCC"),
        ],
    )
    with instance as linbpq:
        with _connect(linbpq, "N0BBB") as first:
            assert _accepted(first), "first partner should be accepted"

            with _connect(linbpq, "N0CCC") as second:
                refused = not _accepted(second)

        assert refused, (
            "second partner was accepted while port 1 was busy; "
            f"log: {_bbs_log(tmp_path)!r}"
        )

        # Give linbpq a moment to notice the first session has gone.
        time.sleep(2)
        with _connect(linbpq, "N0CCC") as second:
            assert _accepted(second), (
                "second partner should be accepted once the port is free; "
                f"log: {_bbs_log(tmp_path)!r}"
            )


def test_no_interlock_allows_concurrent_incoming_partners(tmp_path: Path):
    """Control: without an INTERLOCK line naming the port, two
    partners can be connected at once."""
    instance = _setup(
        tmp_path,
        [
            _partner("N0BBB", connect_script=["C N0BBB"]),
            _partner("N0CCC"),
        ],
    )
    with instance as linbpq:
        with _connect(linbpq, "N0BBB") as first:
            assert _accepted(first)
            with _connect(linbpq, "N0CCC") as second:
                assert _accepted(second), (
                    "second partner refused with no INTERLOCK configured; "
                    f"log: {_bbs_log(tmp_path)!r}"
                )


def _user_login(user) -> tuple[bool, bytes]:
    """Log an ordinary user in and enter the BBS.

    Users get the prompt but no SID.  Returns whether we got the
    prompt, and on failure everything received after asking for the BBS.
    """
    user.read_until(b"user:", timeout=5)
    user.write(user.username.encode() + b"\r")
    user.read_until(b"password:", timeout=5)
    user.write(user.password.encode() + b"\r")
    user.read_until(b"\n", timeout=5)
    user.send_line(b"BBS")
    try:
        user.read_until(b"de N0AAA>", timeout=8)
        return True, b""
    except (TimeoutError, ConnectionResetError):
        return False, bytes(user._buf)


_SORRY = b"Sorry, mail forwarding in progress"


def test_interlock_refuses_ordinary_users_during_mail_run(tmp_path: Path):
    """While a partner holds an interlocked port, an ordinary user
    entering the BBS on it is refused, and told why."""
    instance = _setup(
        tmp_path,
        [_partner("N0BBB", connect_script=["INTERLOCK 1", "C N0BBB"])],
    )
    with instance as linbpq:
        with _connect(linbpq, "N0BBB") as partner:
            assert _accepted(partner)
            # N0CCC has no BBSUsers record here, so it's an ordinary
            # (new) user.
            with _connect(linbpq, "N0CCC") as user:
                got_in, text = _user_login(user)

        assert not got_in, (
            "user got into the BBS during a mail run; "
            f"log: {_bbs_log(tmp_path)!r}"
        )
        assert _SORRY in text, text

        time.sleep(2)
        with _connect(linbpq, "N0CCC") as user:
            assert _user_login(user)[0], (
                "user still refused after the mail run ended; "
                f"log: {_bbs_log(tmp_path)!r}"
            )


def test_interlock_lets_ordinary_users_share_a_port(tmp_path: Path):
    """Only a mail run blocks ordinary users.  Two users can be on an
    interlocked port at once."""
    instance = _setup(
        tmp_path,
        [_partner("N0BBB", connect_script=["INTERLOCK 1", "C N0BBB"])],
    )
    with instance as linbpq:
        with _connect(linbpq, "N0CCC") as first:
            assert _user_login(first)[0]
            with _connect(linbpq, "N0DDD") as second:
                assert _user_login(second)[0], (
                    "second ordinary user refused with no mail run; "
                    f"log: {_bbs_log(tmp_path)!r}"
                )


def test_interlock_refuses_partner_while_user_connected(tmp_path: Path):
    """A partner is refused while anyone else, including an ordinary
    user, is in the BBS on the interlocked port."""
    instance = _setup(
        tmp_path,
        [_partner("N0BBB", connect_script=["INTERLOCK 1", "C N0BBB"])],
    )
    with instance as linbpq:
        with _connect(linbpq, "N0CCC") as user:
            assert _user_login(user)[0]
            with _connect(linbpq, "N0BBB") as partner:
                assert not _accepted(partner), (
                    "partner accepted while a user was on the port; "
                    f"log: {_bbs_log(tmp_path)!r}"
                )


# ----------------------------------------------------------------------
# INTERLOCK GROUP
# ----------------------------------------------------------------------


def test_interlock_group_refuses_partner_on_other_port_in_group(tmp_path: Path):
    """Ports 1 and 2 are both INTERLOCK=1 and a script names
    ``INTERLOCK GROUP 1``.  A partner on port 1 blocks a partner
    connecting in on port 2, until it has gone."""
    instance, port2 = _setup_two_ports(
        tmp_path,
        [
            _partner("N0BBB", connect_script=["INTERLOCK GROUP 1", "C 1 N0BBB"]),
            _partner("N0CCC"),
        ],
        group1=1,
        group2=1,
    )
    with instance as linbpq:
        with _connect(linbpq, "N0BBB") as first:
            assert _accepted(first), "first partner should be accepted"

            with _connect(linbpq, "N0CCC", port2) as second:
                refused = not _accepted(second)

        assert refused, (
            "partner on port 2 accepted while group 1 was busy on port 1; "
            f"log: {_bbs_log(tmp_path)!r}"
        )

        time.sleep(2)
        with _connect(linbpq, "N0CCC", port2) as second:
            assert _accepted(second), (
                "partner should be accepted once the group is free; "
                f"log: {_bbs_log(tmp_path)!r}"
            )


def test_interlock_group_refuses_ordinary_user_on_other_port(tmp_path: Path):
    """A mail run on port 1 blocks an ordinary user entering the BBS
    on port 2 in the same group."""
    instance, port2 = _setup_two_ports(
        tmp_path,
        [_partner("N0BBB", connect_script=["INTERLOCK GROUP 1", "C 1 N0BBB"])],
        group1=1,
        group2=1,
    )
    with instance as linbpq:
        with _connect(linbpq, "N0BBB") as partner:
            assert _accepted(partner)
            with _connect(linbpq, "N0CCC", port2) as user:
                got_in, text = _user_login(user)

    assert not got_in, f"log: {_bbs_log(tmp_path)!r}"
    assert _SORRY in text, text


def test_interlock_group_ports_in_different_groups_are_independent(tmp_path: Path):
    """Port 1 is group 1 and port 2 is group 2.  A session on port 1
    doesn't block port 2."""
    instance, port2 = _setup_two_ports(
        tmp_path,
        [
            _partner("N0BBB", connect_script=["INTERLOCK GROUP 1", "C 1 N0BBB"]),
            _partner("N0CCC", connect_script=["INTERLOCK GROUP 2", "C 2 N0CCC"]),
        ],
        group1=1,
        group2=2,
    )
    with instance as linbpq:
        with _connect(linbpq, "N0BBB") as first:
            assert _accepted(first)
            with _connect(linbpq, "N0CCC", port2) as second:
                assert _accepted(second), (
                    "partner on port 2 refused although it's in another group; "
                    f"log: {_bbs_log(tmp_path)!r}"
                )


def test_interlock_group_not_enforced_unless_named_in_a_script(tmp_path: Path):
    """``INTERLOCK=1`` on its own (no script names ``INTERLOCK GROUP 1``)
    leaves incoming connects alone, so ports that get a lock number
    for other reasons, e.g. rig control, behave as before."""
    instance, port2 = _setup_two_ports(
        tmp_path,
        [_partner("N0BBB", connect_script=["C 1 N0BBB"]), _partner("N0CCC")],
        group1=1,
        group2=1,
    )
    with instance as linbpq:
        with _connect(linbpq, "N0BBB") as first:
            assert _accepted(first)
            with _connect(linbpq, "N0CCC", port2) as second:
                assert _accepted(second), (
                    "partner refused with no script naming the group; "
                    f"log: {_bbs_log(tmp_path)!r}"
                )


def _wait_for_log(work_dir: Path, text: str, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if text in _bbs_log(work_dir):
            return True
        time.sleep(2)
    return False


@pytest.mark.parametrize("busy", [True, False])
def test_interlock_group_abandons_dial_out_when_busy(tmp_path: Path, busy: bool):
    """A dial-out whose script starts ``INTERLOCK GROUP 1`` is abandoned
    while a partner is on a port in group 1, and carries on otherwise.

    The dial-out is started from the web config's Start Forwarding
    button.  The result is only visible in the BBS log, which can take
    over 30s to reach disk."""
    instance, port2 = _setup_two_ports(
        tmp_path,
        [
            _partner("N0BBB"),
            _partner("N0CCC", connect_script=["INTERLOCK GROUP 1", "C 2 N0CCC"]),
        ],
        group1=1,
        group2=1,
    )
    with instance as linbpq:
        with _connect(linbpq, "N0BBB") as holder:
            if busy:
                assert _accepted(holder)

            key = _mail_signon(linbpq.http_port)
            _http_post(linbpq.http_port, f"/Mail/FwdDetails?{key}", b"N0CCC")
            _http_post(linbpq.http_port, f"/Mail/FWDSave?{key}", b"StartForward")

            assert _wait_for_log(tmp_path, "Script INTERLOCK GROUP 1", 60), (
                f"script didn't run; log: {_bbs_log(tmp_path)!r}"
            )
            # The busy line is written straight after the Script line,
            # so they reach disk together.
            busy_logged = "Interlock Group 1 is busy - quitting" in _bbs_log(tmp_path)

    assert busy_logged == busy, _bbs_log(tmp_path)


# ----------------------------------------------------------------------
# MaxSessionTime / SessionLockout
# ----------------------------------------------------------------------


@pytest.mark.long_runtime
def test_max_session_time_cuts_off_and_locks_out(tmp_path: Path):
    """``MaxSessionTime = 1`` cuts a partner session off after one
    minute (plus up to one 10s timer tick).  ``SessionLockout = 1``
    then refuses the partner for a minute, after which it's accepted
    again."""
    instance = _setup(
        tmp_path,
        [_partner("N0BBB", max_session_time=1, session_lockout=1)],
    )
    with instance as linbpq:
        with _connect(linbpq, "N0BBB") as partner:
            assert _accepted(partner)
            # Complete the SID exchange so it counts as a mail session
            # for the duration log.  The answering BBS then waits for
            # us, so the session goes quiet.
            partner.send_sid()
            _wait_for_cutoff(partner, timeout=3)
            partner._buf.clear()
            waited = _wait_for_cutoff(partner, timeout=100)
        cut_at = time.monotonic()

        assert waited is not None, (
            "session wasn't cut off within 100s; "
            f"log: {_bbs_log(tmp_path)!r}"
        )
        assert 55 <= waited <= 85, f"cut off after {waited:.0f}s, expected ~60-70s"

        with _connect(linbpq, "N0BBB") as partner:
            assert not _accepted(partner), (
                "partner accepted during lockout; "
                f"log: {_bbs_log(tmp_path)!r}"
            )

        time.sleep(max(0.0, cut_at + 65 - time.monotonic()))
        with _connect(linbpq, "N0BBB") as partner:
            assert _accepted(partner), (
                "partner still refused after lockout ended; "
                f"log: {_bbs_log(tmp_path)!r}"
            )

    log = _bbs_log(tmp_path)
    assert "exceeded MaxSessionTime" in log, log
    assert "Rejected - locked out" in log, log
    # One duration line: the cut-off session.  The refused connect and
    # the final login (no SID exchange) don't get one.
    durations = re.findall(r"Partner session lasted (\d+) mins \d+ secs(.*)", log)
    assert len(durations) == 1, log
    assert durations[0][0] == "1", log
    assert "cut off by MaxSessionTime" in durations[0][1], log


def test_max_session_time_zero_means_no_limit(tmp_path: Path):
    """Partners without the settings behave as before: an idle partner
    session isn't cut off by the session timer."""
    instance = _setup(tmp_path, [_partner("N0BBB")])
    with instance as linbpq:
        with _connect(linbpq, "N0BBB") as partner:
            assert _accepted(partner)
            assert _wait_for_cutoff(partner, timeout=25) is None


# ----------------------------------------------------------------------
# Web config
# ----------------------------------------------------------------------


def _http_post(port: int, path: str, body: bytes) -> bytes:
    request = (
        f"POST {path} HTTP/1.0\r\n"
        f"Host: 127.0.0.1:{port}\r\n"
        "Accept-Encoding: deflate\r\n"
        "Content-Type: application/x-www-form-urlencoded\r\n"
        f"Content-Length: {len(body)}\r\n\r\n"
    ).encode("ascii") + body
    data = b""
    with socket.create_connection(("127.0.0.1", port), timeout=5) as sock:
        sock.sendall(request)
        while True:
            try:
                chunk = sock.recv(8192)
            except (TimeoutError, socket.timeout):
                break
            if not chunk:
                break
            data += chunk
    head, _, resp = data.partition(b"\r\n\r\n")
    if b"content-encoding: deflate" in head.lower():
        resp = zlib.decompress(resp)
    return resp


def _mail_signon(port: int) -> str:
    body = _http_post(port, "/Mail/Signon?Mail", b"User=test&password=test")
    m = re.search(rb"\?(M[0-9A-F]{12})", body)
    assert m, f"no session key in signon reply: {body[:500]!r}"
    return m.group(1).decode()


def _fwd_fields(page: bytes) -> dict[str, str]:
    return {
        name.decode(): value.decode()
        for value, name in re.findall(rb"value=(\d+) size=3 name=(\w+)", page)
    }


def test_web_config_shows_and_saves_session_limits(tmp_path: Path):
    """The FwdDetail page shows MaxSessionTime and SessionLockout, and
    FWDSave writes both back to linmail.cfg."""
    instance = _setup(
        tmp_path,
        [_partner("N0BBB", max_session_time=5, session_lockout=30)],
    )
    with instance as linbpq:
        key = _mail_signon(linbpq.http_port)

        page = _http_post(linbpq.http_port, f"/Mail/FwdDetails?{key}", b"N0BBB")
        fields = _fwd_fields(page)
        assert fields.get("MaxSess") == "5", page
        assert fields.get("Lockout") == "30", page

        # Same field order as save() in the FwdDetail page script.
        save = "|".join([
            "", "", "", "C N0BBB", "", "", "",   # TO AT Times FWD HRB HRP BBSHA
            "false", "600", "false", "0",        # EnF Interval EnR RInterval
            "false", "true", "256", "false",     # NoWait Blocked FBBBlock Personal
            "true", "true", "true", "true",      # Bin B1 B2 CTRLZ
            "600", "7", "45",                    # ConTimeOut MaxSess Lockout
        ]) + "|"
        page = _http_post(
            linbpq.http_port, f"/Mail/FWDSave?{key}", save.encode("ascii")
        )
        fields = _fwd_fields(page)
        assert fields.get("MaxSess") == "7", page
        assert fields.get("Lockout") == "45", page

    cfg = (tmp_path / "linmail.cfg").read_text()
    assert re.search(r"MaxSessionTime\s*=\s*7;", cfg), cfg
    assert re.search(r"SessionLockout\s*=\s*45;", cfg), cfg
