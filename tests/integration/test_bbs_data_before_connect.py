"""A line that reaches the BBS before its connect is processed (#86).

``PollStreams`` reads each BBS stream's data before it checks the
stream's state.  A USER line whose application field is ``BBS`` starts
the BBS straight after the password; if the client's next line follows
within the same 100 ms poll, the BBS used to read that line with the
stream's old ``ConnectionInfo``.  On a stream never used before that
meant a NULL user and SIGSEGV in ``ProcessLine``, taking the node down.

The fork's fix is in BBSStreamGuard.c: a pending connect is handled
before the data is read.

Timing: a first session ends, then a second login sends user, password
and ``BBS`` as three writes about 1 ms apart on the FBB port.  On
6.0.26.1 that crashed on every attempt.
"""

from __future__ import annotations

import socket
import time
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
    + "".join(f" USER=u{i},u{i},N0A{i},BBS,\n" for i in range(10, 20))
    + "ENDPORT\n"
)


@pytest.fixture
def linbpq_autostart(tmp_path: Path):
    instance = LinbpqInstance(tmp_path, config_template=_CFG, extra_args=("mail",))
    instance.start()
    try:
        yield instance
    finally:
        instance.stop()


def _login(port: int, user: str, gap: float) -> bytes:
    """Send user, password and ``BBS`` as separate writes ``gap`` seconds
    apart, then read for 2 s."""
    with socket.create_connection(("127.0.0.1", port), timeout=3) as sock:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        for line in (user, user, "BBS"):
            sock.sendall(line.encode() + b"\r")
            time.sleep(gap)
        sock.settimeout(0.3)
        buf = b""
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            try:
                chunk = sock.recv(4096)
            except (TimeoutError, socket.timeout):
                continue
            except ConnectionResetError:
                break
            if not chunk:
                break
            buf += chunk
        return buf


def test_line_straight_after_autostart_login_does_not_crash(linbpq_autostart):
    inst = linbpq_autostart
    # The FBB listener opens a little after the telnet one
    deadline = time.monotonic() + 10
    while True:
        try:
            socket.create_connection(("127.0.0.1", inst.fbb_port), timeout=0.5).close()
            break
        except OSError:
            if time.monotonic() > deadline:
                raise
            time.sleep(0.2)
    time.sleep(1)
    for first, second in (("u10", "u11"), ("u12", "u13"), ("u14", "u15")):
        for user, gap in ((first, 0), (second, 0.001)):
            try:
                reply = _login(inst.fbb_port, user, gap)
            except OSError as exc:
                reply = f"<{exc}>".encode()
            time.sleep(0.5)
            assert inst.proc.poll() is None, (
                f"linbpq exited (rc={inst.proc.returncode}) at {user}'s login; "
                f"reply {reply!r}; see {inst.stdout_path}"
            )
            # The BBS got the session: SID, then the new user's name prompt
            # (answered by the extra BBS line, or by the auto-start command).
            assert b"[BPQ-" in reply, f"no BBS SID for {user}: {reply!r}"
            assert b"de N0CALL>" in reply, f"no BBS prompt for {user}: {reply!r}"
