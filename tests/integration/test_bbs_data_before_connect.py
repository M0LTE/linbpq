"""A line that reaches the BBS before its connect is processed (#86).

``PollStreams`` reads each BBS stream's data before it checks the
stream's state.  A USER line whose application field is ``BBS`` starts
the BBS straight after the password; if the client's next line follows
within the same 100 ms poll, the BBS used to read that line with the
stream's old ``ConnectionInfo``:

- on a stream never used before, a NULL user: SIGSEGV in
  ``ProcessLine``, and the node goes down;
- on a stream used before, the previous session's user and state: the
  line ran in the old session (``Invalid Command`` and a prompt before
  the new session's SID).

The fork's fix is in BBSStreamGuard.c: a pending connect is handled
before the data is read, and if the BBS refuses the caller the line is
dropped.

Timing: user, password and the next line go as three writes about 1 ms
apart on the FBB port (for the refused caller, the line 30 ms after the
password), so the connect and the line almost always land in the same
poll.  Without the fix the reused-stream test fails at the first fast
login, the new-stream test crashes linbpq, and the Excluded test sees
the line rename the refused user.
"""

from __future__ import annotations

import re
import socket
import time
import zlib
from pathlib import Path
from string import Template

import pytest

from helpers.linbpq_instance import LinbpqInstance


_CFG = Template(
    """\
SIMPLE=1
NODECALL=N0CALL
NODEALIAS=TEST
LOCATOR=NONE
APPLICATIONS=BBS
BBSCALL=N0CALL
BBSALIAS=BBS

PORT
 ID=Telnet
 DRIVER=Telnet
 CONFIG
 TCPPORT=$telnet_port
 HTTPPORT=$http_port
 FBBPORT=$fbb_port
 MAXSESSIONS=10
 USER=test,test,N0SDR,,SYSOP
"""
    + "".join(f" USER=u{i},u{i},N0A{i},BBS,\n" for i in range(10, 30))
    + "ENDPORT\n"
)


@pytest.fixture
def linbpq_autostart(tmp_path: Path):
    instance = LinbpqInstance(tmp_path, config_template=_CFG, extra_args=("mail",))
    instance.start()
    try:
        # The FBB listener opens a little after the telnet one
        deadline = time.monotonic() + 10
        while True:
            try:
                socket.create_connection(
                    ("127.0.0.1", instance.fbb_port), timeout=0.5
                ).close()
                break
            except OSError:
                if time.monotonic() > deadline:
                    raise
                time.sleep(0.2)
        time.sleep(1)
        yield instance
    finally:
        instance.stop()


def _open(port: int, user: str, line: str, gap: float) -> socket.socket:
    """Log in on the FBB port, sending user, password and ``line`` as
    separate writes ``gap`` seconds apart."""
    sock = socket.create_connection(("127.0.0.1", port), timeout=3)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    for part in (user, user, line):
        sock.sendall(part.encode() + b"\r")
        time.sleep(gap)
    return sock


def _read(sock: socket.socket, seconds: float = 2) -> bytes:
    sock.settimeout(0.3)
    buf = b""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            chunk = sock.recv(4096)
        except (TimeoutError, socket.timeout):
            continue
        except OSError:
            break
        if not chunk:
            break
        buf += chunk
    return buf


def _login(inst, user: str, gap: float, line: str = "BBS", keep: list | None = None) -> bytes:
    try:
        sock = _open(inst.fbb_port, user, line, gap)
        reply = _read(sock)
        if keep is None:
            sock.close()
        else:
            keep.append(sock)
    except OSError as exc:
        reply = f"<{exc}>".encode()
    time.sleep(0.5)
    assert inst.proc.poll() is None, (
        f"linbpq exited (rc={inst.proc.returncode}) at {user}'s login; "
        f"reply {reply!r}; see {inst.stdout_path}"
    )
    return reply


def _assert_own_session(user: str, reply: bytes) -> None:
    """The line went to this user's new session: SID, name prompt
    (answered by the auto-start command or the extra line), welcome, and
    only then a prompt.  No ``Invalid Command`` from an old session."""
    assert b"Invalid Command" not in reply, (
        f"{user}'s line ran in another session: {reply!r}"
    )
    assert b"[BPQ-" in reply, f"no BBS SID for {user}: {reply!r}"
    assert b"Hello " in reply and b"de N0CALL>" in reply, (
        f"no welcome and prompt for {user}: {reply!r}"
    )
    assert reply.index(b"[BPQ-") < reply.index(b"Hello ") < reply.index(b"de N0CALL>"), (
        f"prompt before {user}'s welcome: {reply!r}"
    )


def test_line_after_login_on_a_reused_stream(linbpq_autostart):
    """Each session ends before the next starts, so the fast login lands
    on a stream whose ConnectionInfo still holds the previous user."""
    inst = linbpq_autostart
    for first, second in (("u10", "u11"), ("u12", "u13"), ("u14", "u15")):
        _login(inst, first, 0)
        _assert_own_session(second, _login(inst, second, 0.001))


def test_line_after_login_on_a_new_stream(linbpq_autostart):
    """Earlier sessions stay open, so each fast login gets a BBS stream
    never used before: a NULL user without the fix."""
    inst = linbpq_autostart
    keep: list[socket.socket] = []
    try:
        _login(inst, "u16", 0.5, keep=keep)
        for user in ("u17", "u18", "u19"):
            _assert_own_session(user, _login(inst, user, 0.001, keep=keep))
    finally:
        for sock in keep:
            sock.close()


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
            head, sep, resp = data.partition(b"\r\n\r\n")
            length = re.search(rb"content-length: *(\d+)", head, re.I)
            if sep and length and len(resp) >= int(length.group(1)):
                break
    head, _, resp = data.partition(b"\r\n\r\n")
    if b"content-encoding: deflate" in head.lower():
        resp = zlib.decompress(resp)
    return resp


def _exclude(port: int, call: str) -> None:
    """Create the BBS user ``call`` with the Excluded flag, through the
    mail web pages."""
    body = _http_post(port, "/Mail/Signon?Mail", b"User=test&password=test")
    m = re.search(rb"\?(M[0-9A-F]{12})", body)
    assert m, f"no session key in signon reply: {body[:500]!r}"
    key = m.group(1).decode()
    _http_post(port, f"/Mail/UserSave?{key}", f"Add={call}".encode())
    page = _http_post(port, f"/Mail/UserDetails?{key}", call.encode())
    assert call.encode() in page, page[:500]
    # Field order as in ProcessUserUpdate (BBSHTMLConfig.c)
    fields = [
        "false", "false", "false", "false", "false", "false", "false",  # BBS Email PMS RMSEx SYSOP PollRMS Expert
        "0", "0", "0", "0",                                             # SSIDs
        "true",                                                         # Excluded
        "false", "false", "false", "true", "false", "false", "false",   # Hold SysopLM NoWinlink Bulls NTS RMSRedirect APRSMFor
        "0", "0",                                                       # APRS SSID, Last listed
        "Excluded", "", "", "", "", "",                                 # Name Pass CMSPass QTH ZIP HomeBBS
    ]
    _http_post(port, f"/Mail/UserSave?{key}", "|".join(fields).encode())


def _user_name(port: int, call: str) -> str:
    body = _http_post(port, "/Mail/Signon?Mail", b"User=test&password=test")
    key = re.search(rb"\?(M[0-9A-F]{12})", body).group(1).decode()
    page = _http_post(port, f"/Mail/UserDetails?{key}", call.encode())
    return page.decode("latin-1")


def test_excluded_callers_early_line_is_dropped(linbpq_autostart):
    """The BBS refuses an Excluded user by asking for a disconnect, which
    leaves the session in place for a moment.  A line that came with the
    connect must not run as that user (here ``N Pwned`` would rename
    them)."""
    inst = linbpq_autostart
    for user, call in (("u20", "N0A20"), ("u21", "N0A21"), ("u22", "N0A22"), ("u23", "N0A23")):
        _exclude(inst.http_port, call)
        assert "Excluded" in _user_name(inst.http_port, call)
        # User and password together, then the line 30 ms later: after the
        # node has started the BBS, but inside the same BBS poll.
        with socket.create_connection(("127.0.0.1", inst.fbb_port), timeout=3) as sock:
            sock.sendall(f"{user}\r{user}\r".encode())
            time.sleep(0.03)
            sock.sendall(b"N Pwned\r")
            _read(sock)
        time.sleep(0.5)
        assert inst.proc.poll() is None, f"linbpq exited at {user}'s login"
        page = _user_name(inst.http_port, call)
        assert "Pwned" not in page, f"{call}'s early line ran after the BBS refused them"
