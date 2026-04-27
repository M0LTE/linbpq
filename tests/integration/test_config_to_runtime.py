"""Phase 7 — config-driven values appear in runtime commands.

Several ``bpq32.cfg`` keywords just set runtime variables that the
sysop can later read via the corresponding telnet command (e.g.
``L4WINDOW=8`` in cfg → ``L4WINDOW`` command returns ``L4WINDOW 8``).

These tests exercise the cfg-parser → live-state → command-dispatch
plumbing end-to-end.  A regression in any of those three steps lands
a failure here.
"""

from __future__ import annotations

from pathlib import Path
from string import Template

import pytest

from helpers.linbpq_instance import LinbpqInstance
from helpers.telnet_client import TelnetClient


def _cfg_with_globals(extra_lines: str) -> Template:
    """Build a config template carrying extra top-level cfg lines."""
    base = """\
SIMPLE=1
NODECALL=N0CALL
NODEALIAS=TEST
LOCATOR=NONE
{extra}

PORT
 ID=Telnet
 DRIVER=Telnet
 CONFIG
 TCPPORT=$telnet_port
 HTTPPORT=$http_port
 MAXSESSIONS=10
 USER=test,test,N0CALL,,SYSOP
ENDPORT
""".replace("{extra}", extra_lines)
    return Template(base)


def test_infomsg_block_renders_via_info_command(tmp_path: Path):
    """``INFOMSG: ... ***`` block content shows up in the INFO command."""
    cfg = _cfg_with_globals(
        """INFOMSG:
This is the configured INFOMSG.
Multiple lines work too.
***"""
    )
    with LinbpqInstance(tmp_path, config_template=cfg) as linbpq:
        with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
            client.login("test", "test")
            response = client.run_command("INFO")
    assert b"This is the configured INFOMSG." in response, (
        f"INFOMSG body not echoed by INFO: {response!r}"
    )
    assert b"Multiple lines work too." in response


# (cfg-keyword, value, sysop-command, expected-substring-in-response)
CFG_TO_RUNTIME = [
    pytest.param("L4WINDOW=8", "L4WINDOW", b"L4WINDOW 8", id="L4WINDOW"),
    pytest.param("NODESINTERVAL=15", "NODESINT", b"NODESINT 15", id="NODESINTERVAL"),
    pytest.param("MINQUAL=128", "MINQUAL", b"MINQUAL 128", id="MINQUAL"),
]


@pytest.mark.parametrize("cfg_line,cmd,expected", CFG_TO_RUNTIME)
def test_cfg_global_visible_via_sysop_command(
    tmp_path: Path, cfg_line: str, cmd: str, expected: bytes
):
    """A cfg keyword that just sets a global is read back unchanged
    by the matching sysop command (after PASSWORD unlock)."""
    cfg = _cfg_with_globals(cfg_line)
    with LinbpqInstance(tmp_path, config_template=cfg) as linbpq:
        with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
            client.login("test", "test")
            client.run_command("PASSWORD")
            response = client.run_command(cmd)
    assert expected in response, (
        f"{cmd}: expected {expected!r}; got {response!r}"
    )


# Per-port tuning round-trips: cfg sets a port-level keyword,
# matching ``<CMD> <port>`` sysop command reads back the value.
# Some keywords (TXDELAY, FRACK, RESPTIME) are scaled by linbpq
# before being stored — those aren't trivially round-trip-able
# without modelling the scaling, so we skip them here and lock in
# the ones that round-trip cleanly.
PER_PORT_TUNING = [
    pytest.param("RETRIES=20", "RETRIES 2", b"RETRIES 20", id="RETRIES"),
    pytest.param("MAXFRAME=5", "MAXFRAME 2", b"MAXFRAME 5", id="MAXFRAME"),
    pytest.param("PERSIST=127", "PERSIST 2", b"PERSIST 127", id="PERSIST"),
    pytest.param("DIGIFLAG=1", "DIGIFLAG 2", b"DIGIFLAG 1", id="DIGIFLAG"),
]


_PER_PORT_CFG_TEMPLATE = """\
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
 PORTNUM=2
 ID=AXIP
 DRIVER=BPQAXIP
 {extra}
 CONFIG
 UDP $axip_port
ENDPORT
"""


@pytest.mark.parametrize("cfg_line,cmd,expected", PER_PORT_TUNING)
def test_cfg_per_port_visible_via_sysop_command(
    tmp_path: Path, cfg_line: str, cmd: str, expected: bytes
):
    """A port-level cfg keyword (``RETRIES=N`` etc.) round-trips
    through the matching ``<CMD> <port>`` sysop command."""
    cfg = Template(_PER_PORT_CFG_TEMPLATE.replace("{extra}", " " + cfg_line))
    with LinbpqInstance(tmp_path, config_template=cfg) as linbpq:
        with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
            client.login("test", "test")
            client.run_command("PASSWORD")
            response = client.run_command(cmd)
    assert expected in response, (
        f"{cmd}: expected {expected!r}; got {response!r}"
    )
