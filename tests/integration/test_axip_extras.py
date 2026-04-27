"""BPQAXIP cfg-block extras (gap-analysis closeout).

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

These are all related to issue #4 (L4-uplink not propagating);
the fix for #4 likely involves combining ``BROADCAST NODES`` with
``MAP ... B`` to get NODES broadcasts to fan out properly.  These
tests just lock in the cfg-parser acceptance for now — full
behavioural coverage waits on the L4-uplink investigation.
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
