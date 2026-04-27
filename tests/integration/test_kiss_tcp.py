"""Phase 2 deferral — linbpq connects out as a KISS-TCP client.

linbpq doesn't expose a KISS-TCP server itself; rather it acts as a
client connecting out over TCP to a KISS source.  The peer can be a
softmodem with a TCP listener (Direwolf, UZ7HO) or a serial-to-TCP
bridge (m0lte/kissproxy, exposing e.g. a NinoTNC over TCP).

The wire side we test is the *outbound* TCP connection: configure
linbpq with ``TYPE=ASYNC PROTOCOL=KISS IPADDR TCPPORT`` pointing at
a tiny Python listener and verify the daemon connects.
"""

from __future__ import annotations

from pathlib import Path
from string import Template

from helpers.kiss_tcp_server import kiss_tcp_server
from helpers.linbpq_instance import LinbpqInstance


# Custom config: standard Telnet block (so we can prove linbpq finished
# starting and the AX.25 stack came up) plus a second PORT that is a
# KISS-TCP client pointing at the test fixture.  PORTNUM=2 is explicit
# so the AX.25 stack knows to associate this slot with the new port.
KISS_TCP_CLIENT_CONFIG = Template(
    """\
SIMPLE=1
NODECALL=N0CALL
NODEALIAS=TEST
LOCATOR=NONE

PORT
 PORTNUM=1
 ID=Telnet
 DRIVER=Telnet
 CONFIG
 TCPPORT=$telnet_port
 HTTPPORT=$http_port
 MAXSESSIONS=10
 USER=test,test,N0CALL,,SYSOP
ENDPORT

PORT
 PORTNUM=2
 ID=KissOverTcp
 TYPE=ASYNC
 PROTOCOL=KISS
 IPADDR=127.0.0.1
 TCPPORT=$kiss_tcp_port
ENDPORT
"""
)


def test_linbpq_connects_to_kiss_tcp_server(tmp_path: Path):
    with kiss_tcp_server() as server:
        # Render the server's chosen port into the cfg.  We extend
        # LinbpqInstance's substitution dict via a Template subclass
        # that adds $kiss_tcp_port.
        class _Config(Template):
            def substitute(self, **kw):
                return Template.substitute(
                    self, kiss_tcp_port=server.port, **kw
                )

        cfg = _Config(KISS_TCP_CLIENT_CONFIG.template)

        with LinbpqInstance(tmp_path, config_template=cfg):
            assert server.wait_for_client(timeout=10.0), (
                "linbpq did not connect to the KISS-TCP server within 10s"
            )
