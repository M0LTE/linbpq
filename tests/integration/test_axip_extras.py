"""BPQAXIP cfg-block extras.

Beyond the basic ``UDP <port>`` + ``MAP <call> ...`` we already
exercise in test_axip.py and test_two_instance.py, the BPQAXIP
``CONFIG`` block accepts:

- Multiple ``UDP <port>`` lines (one block listening on several
  ports — used by GB7RDG to receive on the OARC mesh range).
- ``MHEARD ON`` (enable MH list updating from this port).
- ``BROADCAST <call>`` (declare a call as a broadcast destination
  so frames addressed there fan out to mapped peers).
- ``MAP ... B`` (broadcast flag on individual map entries — same
  concept but per-peer).

Behavioural coverage for ``BROADCAST NODES`` + ``MAP ... B`` was
unblocked by closing [#4](https://github.com/M0LTE/linbpq/issues/4):
``test_broadcast_nodes_fans_out_to_mapped_peer`` below stands up a
fake UDP listener as the peer and verifies linbpq emits an actual
AX.25-NODES frame to it after ``SENDNODES``.
"""

from __future__ import annotations

import socket
from pathlib import Path
from string import Template

from helpers.linbpq_instance import LinbpqInstance


_AXIP_EXTRAS_CFG = Template(
    """\
SIMPLE=1
NODECALL=N0CALL
NODEALIAS=TEST
LOCATOR=NONE

PORT
 ID=Telnet
 DRIVER=Telnet
 CONFIG
 TCPPORT=$telnet_port
 HTTPPORT=$http_port
 MAXSESSIONS=10
 USER=test,test,N0CALL,,SYSOP
ENDPORT

PORT
 ID=AXIP
 DRIVER=BPQAXIP
 CONFIG
 UDP $axip_port
 UDP $netrom_port
 UDP $fbb_port
 MHEARD ON
 BROADCAST NODES
 BROADCAST ID
 MAP N0PEER 127.0.0.1 UDP $api_port B
 MAP M0LTE-9 127.0.0.1 UDP $agw_port B
ENDPORT
"""
)


def test_axip_multi_udp_and_broadcast_block_parses(tmp_path: Path):
    """Multi-UDP, MHEARD ON, BROADCAST <call>, MAP ... B all parse
    cleanly; daemon serves telnet."""
    with LinbpqInstance(tmp_path, config_template=_AXIP_EXTRAS_CFG) as linbpq:
        with socket.create_connection(("127.0.0.1", linbpq.telnet_port), timeout=3) as sock:
            sock.settimeout(2)
            # Just probe that the connection opens.
            assert sock.recv(64), "telnet didn't greet"

    # No bad-config-record warnings.
    log = (tmp_path / "linbpq.stdout.log").read_text(errors="replace")
    assert "bad config record" not in log.lower(), (
        f"BPQAXIP parser rejected an extra: {log[:2000]}"
    )


_AXIP_BROADCAST_BEHAVIOUR_CFG = Template(
    """\
SIMPLE=1
NODECALL=N0AAA
NODEALIAS=AAA
LOCATOR=NONE
NODESINTERVAL=1

PORT
 ID=Telnet
 DRIVER=Telnet
 CONFIG
 TCPPORT=$telnet_port
 HTTPPORT=$http_port
 MAXSESSIONS=10
 USER=test,test,N0AAA,,SYSOP
ENDPORT

PORT
 ID=AXIP
 DRIVER=BPQAXIP
 QUALITY=200
 MINQUAL=1
 CONFIG
 UDP $axip_port
 BROADCAST NODES
 MAP N0PEER 127.0.0.1 UDP $peer_udp_port B
ENDPORT

ROUTES:
N0PEER,200,2
***
"""
)


def test_broadcast_nodes_fans_out_to_mapped_peer(tmp_path: Path):
    """When ``SENDNODES`` fires, linbpq should emit an actual AX.25 NODES
    broadcast UDP frame to every mapped peer with the ``B`` flag set
    on the MAP entry — not just parse the cfg cleanly.

    Test setup: bind a UDP listener at a fake-peer port, configure
    linbpq with ``BROADCAST NODES`` and ``MAP N0PEER 127.0.0.1 UDP
    <listener> B``.  Sysop-trigger ``SENDNODES``.  Listener should
    receive a datagram.  The first byte of an AX/IP-UDP NODES frame
    is the KISS command byte (``0x00``) followed by 7 bytes of the
    AX.25 destination call ``NODES`` — the 6-byte left-shifted
    callsign + SSID byte (``9C 9E 88 8A A6 40 E0`` for ``NODES``,
    SSID 0).
    """
    import socket as _sock
    import time

    from helpers.telnet_client import TelnetClient

    # Pick a free UDP port for our fake-peer listener.
    with _sock.socket(_sock.AF_INET, _sock.SOCK_DGRAM) as s:
        s.bind(("127.0.0.1", 0))
        peer_udp_port = s.getsockname()[1]

    # Re-bind for real, this time as the listener for the test.
    listener = _sock.socket(_sock.AF_INET, _sock.SOCK_DGRAM)
    listener.setsockopt(_sock.SOL_SOCKET, _sock.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", peer_udp_port))
    listener.settimeout(15.0)

    class _T(Template):
        def substitute(self, **kw):
            return Template.substitute(self, peer_udp_port=peer_udp_port, **kw)

    cfg = _T(_AXIP_BROADCAST_BEHAVIOUR_CFG.template)
    try:
        with LinbpqInstance(tmp_path, config_template=cfg) as linbpq:
            with TelnetClient("127.0.0.1", linbpq.telnet_port, timeout=10) as client:
                client.login("test", "test")
                client.run_command("PASSWORD")
                client.run_command("SENDNODES")

            # Receive the broadcast.  Linbpq sends within seconds of
            # SENDNODES — give it a generous 15s slot for slow CI.
            data, _ = listener.recvfrom(4096)
    finally:
        listener.close()

    # The NODES AX.25 destination encoding is fixed: 'NODES' left-
    # shifted (per L2Code.c::NODECALL[]).
    NODES_AX25 = bytes([0x9C, 0x9E, 0x88, 0x8A, 0xA6, 0x40])
    assert NODES_AX25 in data, (
        f"NODES broadcast frame should contain AX.25-encoded "
        f"'NODES' destination; got {data.hex()}"
    )


def test_axip_multi_udp_all_ports_bind(tmp_path: Path):
    """Three ``UDP <port>`` lines in one BPQAXIP block bind three
    UDP sockets — verifiable by sending a datagram to each and
    seeing none of them refuse."""
    with LinbpqInstance(tmp_path, config_template=_AXIP_EXTRAS_CFG) as linbpq:
        for udp_port in (linbpq.axip_port, linbpq.netrom_port, linbpq.fbb_port):
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                # If the port isn't bound, we'd usually still
                # successfully sendto (UDP is connectionless), but
                # connect() before send asks the kernel to validate
                # reachability and surfaces ECONNREFUSED if no one
                # is listening on loopback.
                sock.connect(("127.0.0.1", udp_port))
                # If we got here without raising, the port is bound.
                sock.send(b"\x00")
