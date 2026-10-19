"""AGW port numbering: strict-xfail tests for M0LTE/linbpq#78.

AGWAPI.c numbers ports differently depending on the frame kind:

- 'G' (port list) reports NUMBEROFPORTS, hidden ports included, but
  lists only the visible ones.
- 'C' / 'v' (connect) treats the port byte as an index into the
  visible ports, and a byte past the end silently falls back to the
  first port.
- 'M' / 'K' (send UI / raw) treat the port byte as a config slot.
- Monitored frames and inbound connections are reported on
  PORTNUM - 1.

They only agree when no port is hidden and the PORTNUMs run 1..N in
config order.  These tests set up ports that break that assumption
(PORTNUM 1, 4, 2 in config order, the example from the issue) and
check that a client can answer on the port byte it was given:

| Test | Covers |
|---|---|
| hidden_port_list | 'G' count matches the entries listed |
| ui_heard_port | a UI heard on byte N can be answered with 'M' on byte N |
| inbound_connect_port | a call arriving on byte N can be returned with 'C' on byte N |
| out_of_range_connect | 'C' on a byte past the listed ports is refused |

Each test asserts the CORRECT behaviour, so it fails today and is
strict-xfailed.  Once #78 is fixed the test passes, strict-xfail
turns that into XPASS, the suite fails, and the xfail has to be
removed.

The two-instance tests link A and B over AX/IP-UDP with an AGW
application call on each side, as in test_two_instance_agw_tunnel.py.
"""

from __future__ import annotations

import socket
import time
from contextlib import ExitStack, contextmanager
from pathlib import Path
from string import Template

import pytest

from helpers.agw_client import AgwFrame, AgwSession
from helpers.linbpq_instance import LinbpqInstance


A_APPL_CALL = "N0AAA-9"
B_APPL_CALL = "N0BBB-9"

# (kind, PORTNUM) in config order.  MIXED is the issue's example:
# the AXIP port is second in config order but has PORTNUM 4, so its
# visible index and slot (1) differ from PORTNUM - 1 (3).  The
# loopback port is only there to fill PORTNUM 2.
MIXED = (("telnet", 1), ("axip", 4), ("loopback", 2))

_XFAIL_REASON = "M0LTE/linbpq#78: AGW mixes three port numberings"


def _port_block(kind: str, portnum: int, node_call: str, *,
                hide: bool = False, peer_axip_port: int = 0) -> str:
    lines = ["PORT", f" PORTNUM={portnum}"]
    if hide:
        lines.append(" HIDE=1")
    if kind == "telnet":
        lines += [
            " ID=Telnet",
            " DRIVER=Telnet",
            " CONFIG",
            " TCPPORT=$telnet_port",
            " HTTPPORT=$http_port",
            " NETROMPORT=$netrom_port",
            " FBBPORT=$fbb_port",
            " APIPORT=$api_port",
            " MAXSESSIONS=20",
            f" USER=test,test,{node_call},,SYSOP",
        ]
    elif kind == "axip":
        peer_appl_call = B_APPL_CALL if node_call == "N0AAA" else A_APPL_CALL
        lines += [
            " ID=AXIP",
            " DRIVER=BPQAXIP",
            " CONFIG",
            " UDP $axip_port",
            f" MAP {peer_appl_call} 127.0.0.1 UDP {peer_axip_port} B",
        ]
    elif kind == "loopback":
        lines += [" ID=Loopback", " TYPE=INTERNAL"]
    else:
        raise ValueError(kind)
    lines.append("ENDPORT")
    return "\n".join(lines) + "\n"


def _config(node_call: str, appl_call: str, layout, *,
            hidden: tuple[str, ...] = (), peer_axip_port: int = 0) -> Template:
    """A node with AGW listening for ``appl_call`` and the ports in
    ``layout`` order.  Instance ports stay as $placeholders for
    LinbpqInstance to fill in."""
    alias = node_call[-3:]
    head = (
        "SIMPLE=1\n"
        f"NODECALL={node_call}\n"
        f"NODEALIAS={alias}\n"
        "LOCATOR=NONE\n"
        "AGWPORT=$agw_port\n"
        "AGWSESSIONS=10\n"
        "AGWMASK=1\n"
        f"APPLICATIONS=APP{alias}\n"
        f"APPL1CALL={appl_call}\n"
        f"APPL1ALIAS=APP{alias}\n\n"
    )
    blocks = [
        _port_block(kind, portnum, node_call, hide=kind in hidden,
                    peer_axip_port=peer_axip_port)
        for kind, portnum in layout
    ]
    return Template(head + "\n".join(blocks))


@contextmanager
def _linked_pair(tmp_path: Path, layout_a, layout_b):
    """Start A and B, each AXIP-mapped to the other's APPL call."""
    a = LinbpqInstance(tmp_path / "A")
    b = LinbpqInstance(tmp_path / "B")
    a.config_template = _config("N0AAA", A_APPL_CALL, layout_a,
                                peer_axip_port=b.axip_port)
    b.config_template = _config("N0BBB", B_APPL_CALL, layout_b,
                                peer_axip_port=a.axip_port)
    with ExitStack() as stack:
        a.start(ready_timeout=15.0)
        stack.callback(a.stop)
        b.start(ready_timeout=15.0)
        stack.callback(b.stop)
        yield a, b


def _agw(instance: LinbpqInstance, call: str) -> AgwSession:
    """Open an AGW session and register ``call``.  The AGW listener
    can come up a moment after telnet, so retry the TCP connect."""
    deadline = time.monotonic() + 10.0
    while True:
        try:
            session = AgwSession.connect("127.0.0.1", instance.agw_port)
            break
        except OSError:
            if time.monotonic() > deadline:
                raise
            time.sleep(0.1)
    session.register(call)
    return session


def _port_list(session: AgwSession) -> tuple[int, list[str]]:
    """Send 'G'; return (reported count, listed entries)."""
    session.send(AgwFrame(0, b"G", 0, b"", b"", b""))
    reply = session.recv()
    assert reply.data_kind == b"G", reply
    fields = reply.data.rstrip(b"\x00").decode("ascii").split(";")
    return int(fields[0]), [f for f in fields[1:] if f.strip()]


def _listed_index(session: AgwSession, port_id: str) -> int:
    """Position of the port whose description is ``port_id`` in the
    'G' list, which is the byte 'C' uses today."""
    _count, entries = _port_list(session)
    for i, entry in enumerate(entries):
        if entry.endswith(f" with {port_id}"):
            return i
    raise AssertionError(f"{port_id} not in AGW port list {entries}")


def _wait_frame(session: AgwSession, match, timeout: float):
    """Return the first frame for which ``match(frame)`` is true, or
    None if none arrives within ``timeout``."""
    deadline = time.monotonic() + timeout
    prev = session.sock.gettimeout()
    session.sock.settimeout(0.5)
    try:
        while time.monotonic() < deadline:
            try:
                frame = session.recv()
            except (TimeoutError, socket.timeout):
                continue
            if match(frame):
                return frame
        return None
    finally:
        session.sock.settimeout(prev)


def _is_connected(frame) -> bool:
    return frame.data_kind == b"C" and b"CONNECTED" in frame.data.upper()


def _ui(session: AgwSession, port: int, callfrom: str, callto: str,
        text: bytes) -> None:
    session.send(AgwFrame(port, b"M", 0xF0, callfrom.encode(),
                          callto.encode(), text))


def _monitored(text: bytes):
    return lambda f: f.data_kind == b"U" and text in f.data


# -- Tests ----------------------------------------------------------


@pytest.mark.xfail(strict=True, reason=f"{_XFAIL_REASON} ('G' count)")
def test_agw_port_numbering_hidden_port_list(tmp_path: Path):
    """With a hidden port, 'G' reports NUMBEROFPORTS (hidden ports
    included) but lists only the visible ports, so the count and the
    list disagree.  Correct: the count equals the number of entries.

    Remove the xfail when #78 is fixed.
    """
    layout = (("telnet", 1), ("axip", 2), ("loopback", 3))
    instance = LinbpqInstance(tmp_path)
    instance.config_template = _config("N0AAA", A_APPL_CALL, layout,
                                       hidden=("axip",))
    with instance:
        with _agw(instance, A_APPL_CALL) as app:
            count, entries = _port_list(app)
    assert not any("AXIP" in e for e in entries), (
        f"hidden AXIP port was listed: {entries}"
    )
    assert count == len(entries), (
        f"'G' reports {count} ports but lists {len(entries)}: {entries}"
    )


@pytest.mark.xfail(strict=True, reason=f"{_XFAIL_REASON} ('M' vs heard)")
def test_agw_port_numbering_ui_heard_port(tmp_path: Path):
    """A UI frame heard on B's AXIP port (PORTNUM 4, second in config
    order) is reported on PORTNUM - 1 = 3, but 'M' takes the byte as
    a config slot, so a UI sent back on byte 3 goes nowhere.
    Correct: the byte a frame is heard on is the byte that sends out
    of the same port, so B's answer reaches A.

    Remove the xfail when #78 is fixed.
    """
    with _linked_pair(tmp_path, MIXED, MIXED) as (a, b):
        with _agw(a, A_APPL_CALL) as app_a, _agw(b, B_APPL_CALL) as app_b:
            a_axip = _listed_index(app_a, "AXIP")
            app_a.send(AgwFrame(0, b"m", 0, b"", b"", b""))
            app_b.send(AgwFrame(0, b"m", 0, b"", b"", b""))

            _ui(app_a, a_axip, A_APPL_CALL, B_APPL_CALL, b"probe-a2b")
            heard = _wait_frame(app_b, _monitored(b"probe-a2b"), 10.0)
            assert heard is not None, "B never heard A's UI frame"

            _ui(app_b, heard.port, B_APPL_CALL, A_APPL_CALL, b"probe-b2a")
            answer = _wait_frame(app_a, _monitored(b"probe-b2a"), 5.0)

    assert answer is not None, (
        f"B heard A on AGW port {heard.port}, but a UI frame sent back "
        f"on port {heard.port} never reached A"
    )


@pytest.mark.xfail(strict=True, reason=f"{_XFAIL_REASON} ('C' vs inbound)")
def test_agw_port_numbering_inbound_connect_port(tmp_path: Path):
    """A call arriving on B's AXIP port (PORTNUM 4) is reported on
    PORTNUM - 1 = 3, but 'C' takes the byte as a visible index, and 3
    is past B's three listed ports, so calling back on it goes out of
    the first port (Telnet) instead.  Correct: the byte a call arrives
    on is the byte that calls out of the same port, so B's call back
    reaches A.

    Remove the xfail when #78 is fixed.
    """
    with _linked_pair(tmp_path, MIXED, MIXED) as (a, b):
        with _agw(a, A_APPL_CALL) as app_a, _agw(b, B_APPL_CALL) as app_b:
            a_axip = _listed_index(app_a, "AXIP")
            app_a.connect_call(a_axip, A_APPL_CALL, B_APPL_CALL)
            assert _wait_frame(app_a, _is_connected, 10.0), (
                "A's call to B did not connect"
            )
            inbound = _wait_frame(app_b, _is_connected, 10.0)
            assert inbound is not None, "B did not see A's call"

            app_a.send(AgwFrame(a_axip, b"d", 0, A_APPL_CALL.encode(),
                                B_APPL_CALL.encode(), b""))
            assert _wait_frame(app_b, lambda f: f.data_kind == b"d", 10.0), (
                "B did not see A disconnect"
            )

            app_b.connect_call(inbound.port, B_APPL_CALL, A_APPL_CALL)
            back = _wait_frame(app_a, _is_connected, 10.0)

    assert back is not None, (
        f"A's call reached B on AGW port {inbound.port}, but B's call "
        f"back on port {inbound.port} never reached A"
    )


@pytest.mark.xfail(strict=True, reason=f"{_XFAIL_REASON} (out-of-range 'C')")
def test_agw_port_numbering_out_of_range_connect(tmp_path: Path):
    """'C' on a port byte past the listed ports reads an unset entry
    of VisiblePortToRealPort and goes out of the first port with no
    error.  Here A's first port is AXIP, so the call reaches B.
    Correct: the call is refused and never leaves A.

    Remove the xfail when #78 is fixed.
    """
    layout_a = (("axip", 1), ("telnet", 2))
    with _linked_pair(tmp_path, layout_a, MIXED) as (a, b):
        with _agw(a, A_APPL_CALL) as app_a, _agw(b, B_APPL_CALL) as app_b:
            _count, entries = _port_list(app_a)
            app_a.connect_call(len(entries), A_APPL_CALL, B_APPL_CALL)
            reached_b = _wait_frame(app_b, _is_connected, 5.0)
            connected_a = _wait_frame(app_a, _is_connected, 1.0)

    assert reached_b is None and connected_a is None, (
        f"'C' on AGW port {len(entries)}, past the {len(entries)} listed "
        f"ports, connected to B instead of being refused"
    )
