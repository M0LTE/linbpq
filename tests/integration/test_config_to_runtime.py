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
    # PACLEN is the port-level cfg keyword; PPACLEN is the sysop
    # read-back command (the bare PACLEN command reads the *session*
    # paclen, a different field).  Round-trips 1:1.
    pytest.param("PACLEN=160", "PPACLEN 2", b"PPACLEN 160", id="PACLEN-PPACLEN"),
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


def test_new_application_line_format_registers_command(tmp_path: Path):
    """The newer ``APPLICATION n,CMD,New,Call,Alias,Quality,L2Alias``
    line registers a command word that appears in ``?`` and
    dispatches (rejection is fine — "Sorry, Application X is not
    running"; the point is the parser wired the alias)."""
    cfg = _cfg_with_globals("APPLICATION 1,WIDGET,,N0CALL-2,WGT,255")
    with LinbpqInstance(tmp_path, config_template=cfg) as linbpq:
        with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
            client.login("test", "test")
            help_response = client.run_command("?")
            widget_response = client.run_command("WIDGET")
    assert b"WIDGET" in help_response, (
        f"WIDGET not in '?' output: {help_response!r}"
    )
    assert b"WIDGET" in widget_response, (
        f"WIDGET not dispatched: {widget_response!r}"
    )
    # We don't have an app actually running on N0CALL-2; that's fine.
    assert (
        b"is not running" in widget_response
        or b"Connected to" in widget_response
    ), f"unexpected WIDGET response: {widget_response!r}"


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


# Scaled per-port tuning: cfg value is in milliseconds, the sysop
# command reports the stored byte value (scaled).  Empirically
# verified with two cfg values each:
#
#   TXDELAY=300  → cmd "TXDELAY 30"   (scale /10)
#   TXDELAY=500  → cmd "TXDELAY 50"
#   TXTAIL=50    → cmd "TXTAIL 5"     (scale /10)
#   TXTAIL=120   → cmd "TXTAIL 12"
#
# FRACK and RESPTIME have non-trivial scaling we don't model here
# (FRACK=2000 → 6, FRACK=3300 → 9 — neither cleanly divisible);
# they're skipped to avoid pinning a fragile invariant.
PER_PORT_SCALED_TUNING = [
    pytest.param("TXDELAY=300", "TXDELAY 2", b"TXDELAY 30", id="TXDELAY-300"),
    pytest.param("TXDELAY=500", "TXDELAY 2", b"TXDELAY 50", id="TXDELAY-500"),
    pytest.param("TXTAIL=50", "TXTAIL 2", b"TXTAIL 5", id="TXTAIL-50"),
    pytest.param("TXTAIL=120", "TXTAIL 2", b"TXTAIL 12", id="TXTAIL-120"),
]


@pytest.mark.parametrize("cfg_line,cmd,expected", PER_PORT_SCALED_TUNING)
def test_cfg_per_port_scaled_round_trip(
    tmp_path: Path, cfg_line: str, cmd: str, expected: bytes
):
    """Scaled per-port keywords (TXDELAY, TXTAIL — both in 10ms
    units stored as bytes) round-trip via the sysop command."""
    cfg = Template(_PER_PORT_CFG_TEMPLATE.replace("{extra}", " " + cfg_line))
    with LinbpqInstance(tmp_path, config_template=cfg) as linbpq:
        with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
            client.login("test", "test")
            client.run_command("PASSWORD")
            response = client.run_command(cmd)
    assert expected in response, (
        f"{cmd}: expected {expected!r}; got {response!r}"
    )


# Per-port keywords with no read-back sysop command — we only
# assert the cfg parser accepts them and the daemon boots clean.
PER_PORT_ACCEPTED_ONLY = [
    pytest.param("SLOTTIME=100", id="SLOTTIME"),
    pytest.param("NODESPACLEN=200", id="NODESPACLEN"),
    pytest.param(
        "M0LTEMapInfo=RF,144.9375,QPSK,1800,3600,Mixed",
        id="M0LTEMapInfo",
    ),
]


@pytest.mark.parametrize("cfg_line", PER_PORT_ACCEPTED_ONLY)
def test_cfg_per_port_accepted_canary(tmp_path: Path, cfg_line: str):
    """Per-port cfg keyword parses cleanly; daemon serves telnet.

    There's no matching ``<CMD> <port>`` sysop command (or the
    command reports a different field than the cfg keyword sets),
    so we only canary the cfg-parser acceptance — the test goes
    red if a refactor silently drops the keyword.
    """
    cfg = Template(_PER_PORT_CFG_TEMPLATE.replace("{extra}", " " + cfg_line))
    with LinbpqInstance(tmp_path, config_template=cfg) as linbpq:
        with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
            client.login("test", "test")
            response = client.run_command("VERSION")
        assert b"Version" in response
    log = (tmp_path / "linbpq.stdout.log").read_text(errors="replace")
    keyword = cfg_line.split("=")[0]
    assert f"Ignored:{keyword}" not in log and (
        f"Ignored: {keyword}" not in log
    ), f"{keyword} got 'not recognised - Ignored': {log[:2000]}"
