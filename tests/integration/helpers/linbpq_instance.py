"""Spawn / control a linbpq process for integration tests."""

from __future__ import annotations

import os
import socket
import subprocess
import time
from pathlib import Path
from string import Template

LINBPQ_BIN = os.environ.get("LINBPQ_BIN", "linbpq")

# A bpq32.cfg that boots cleanly with the standard set of interfaces
# enabled, no radio, all on loopback.  See notes/plan.md.
#
# Telnet/HTTP/NETROM/FBB/API all share one DRIVER=Telnet PORT block
# (TelnetV6.c hands them the same CONFIG section).  AGW is a separate
# global keyword.  AX/IP UDP gets its own DRIVER=BPQAXIP PORT block.
# KISS-TCP needs an external softmodem (Direwolf / UZ7HO) so cannot
# be added to a self-contained test config.
DEFAULT_CONFIG = Template(
    """\
SIMPLE=1
NODECALL=N0CALL
NODEALIAS=TEST
LOCATOR=IO91WJ
AGWPORT=$agw_port

PORT
 ID=Telnet
 DRIVER=Telnet
 CONFIG
 TCPPORT=$telnet_port
 HTTPPORT=$http_port
 NETROMPORT=$netrom_port
 FBBPORT=$fbb_port
 APIPORT=$api_port
 MAXSESSIONS=10
 USER=test,test,N0CALL,,SYSOP
 USER=user,user,N0USER,,
ENDPORT

PORT
 ID=AXIP
 DRIVER=BPQAXIP
 CONFIG
 UDP $axip_port
ENDPORT
"""
)

# Backwards-compat alias for any earlier tests that imported MINIMAL_CONFIG.
MINIMAL_CONFIG = DEFAULT_CONFIG


# Two-instance config with BBS enabled — used to exercise BBS over
# a cross-instance NET/ROM-via-AX/IP-UDP link (a user on A connects
# to B downlink, enters B's BBS, posts a message; another session
# on B reads it back locally).
PEER_MAIL_CONFIG = Template(
    """\
SIMPLE=1
NODECALL=$node_call
NODEALIAS=$node_alias
LOCATOR=NONE
APPLICATIONS=BBS
BBSCALL=$bbs_call
BBSALIAS=BBS
APPL1CALL=$bbs_call
APPL1ALIAS=BBS

PORT
 ID=Telnet
 DRIVER=Telnet
 CONFIG
 TCPPORT=$telnet_port
 HTTPPORT=$http_port
 NETROMPORT=$netrom_port
 FBBPORT=$fbb_port
 APIPORT=$api_port
 MAXSESSIONS=10
 USER=test,test,$node_call,,SYSOP
ENDPORT

PORT
 ID=AXIP
 DRIVER=BPQAXIP
 QUALITY=200
 MINQUAL=1
 CONFIG
 UDP $axip_port
 BROADCAST NODES
 MAP $peer_call 127.0.0.1 UDP $peer_axip_port B
ENDPORT

ROUTES:
$peer_call,200,2
***
"""
)


# Two-instance config used for AX/IP-over-UDP topology tests.  The
# template substitutions add the *peer*'s callsign and UDP port so the
# instance can MAP it.  $node_call / $node_alias / $bbs_call are
# parametrised so the two instances have distinct identities.
PEER_CONFIG = Template(
    """\
SIMPLE=1
NODECALL=$node_call
NODEALIAS=$node_alias
LOCATOR=NONE
NODESINTERVAL=1

PORT
 ID=Telnet
 DRIVER=Telnet
 CONFIG
 TCPPORT=$telnet_port
 HTTPPORT=$http_port
 NETROMPORT=$netrom_port
 FBBPORT=$fbb_port
 APIPORT=$api_port
 MAXSESSIONS=10
 USER=test,test,$node_call,,SYSOP
ENDPORT

PORT
 ID=AXIP
 DRIVER=BPQAXIP
 QUALITY=200
 MINQUAL=1
 CONFIG
 UDP $axip_port
 BROADCAST NODES
 MAP $peer_call 127.0.0.1 UDP $peer_axip_port B
ENDPORT

ROUTES:
$peer_call,200,2
***
"""
)


# DEFAULT_CONFIG variant with the BPQ IP-gateway feature enabled.
# Adds a minimal IPGATEWAY block (LAN adapter with a private-range
# IP+netmask) so the PING / ARP / NAT / IPROUTE / AXMHEARD /
# AXRESOLVER node-prompt commands light up.  No real network is
# touched — the gateway just maintains an in-memory ARP / route
# table, which is what we want for tests.
IP_GATEWAY_CONFIG = Template(
    """\
SIMPLE=1
NODECALL=N0CALL
NODEALIAS=TEST
LOCATOR=IO91WJ
AGWPORT=$agw_port

PORT
 ID=Telnet
 DRIVER=Telnet
 CONFIG
 TCPPORT=$telnet_port
 HTTPPORT=$http_port
 NETROMPORT=$netrom_port
 FBBPORT=$fbb_port
 APIPORT=$api_port
 MAXSESSIONS=10
 USER=test,test,N0CALL,,SYSOP
ENDPORT

PORT
 ID=AXIP
 DRIVER=BPQAXIP
 CONFIG
 UDP $axip_port
ENDPORT

IPGATEWAY
ADAPTER 192.168.99.1 255.255.255.0
****
"""
)


# Pre-canned chatconfig.cfg that puts Chat in application slot 1
# (BBS conventionally takes slot 2 when both run; chat-only setups
# tend to take slot 1).  Pre-writing this file prevents linbpq from
# generating its own default with ApplNum=2 which won't match the
# bpq32.cfg APPLICATIONS=CHAT slot we configure.
CHAT_CONFIG_FILE = """\
Chat :
{
  ApplNum = 1;
  MaxStreams = 10;
  reportChatEvents = 0;
  chatPaclen = 236;
  OtherChatNodes = "";
  ChatWelcomeMsg = "Welcome to the test chat node!";
  MapPosition = "";
  MapPopup = "";
  PopupMode = 0;
};
"""


# Like DEFAULT_CONFIG but with the Chat application registered so the
# telnet "CHAT" alias enters the chat subsystem.  Used together with
# ``LinbpqInstance(..., extra_args=("chat",))`` plus the
# ``CHAT_CONFIG_FILE`` pre-written into the work dir.
CHAT_CONFIG = Template(
    """\
SIMPLE=1
NODECALL=N0CALL
NODEALIAS=TEST
LOCATOR=IO91WJ
APPLICATIONS=CHAT
APPL1CALL=N0CHAT
APPL1ALIAS=CHT

PORT
 ID=Telnet
 DRIVER=Telnet
 CONFIG
 TCPPORT=$telnet_port
 HTTPPORT=$http_port
 MAXSESSIONS=10
 USER=test,test,N0CALL,,SYSOP
ENDPORT
"""
)


# Like DEFAULT_CONFIG but with the BBS application registered so the
# telnet "BBS" alias enters BPQMail.  Used together with
# ``LinbpqInstance(..., extra_args=("mail",))`` to start linbpq with
# its mail subsystem.
MAIL_CONFIG = Template(
    """\
SIMPLE=1
NODECALL=N0CALL
NODEALIAS=TEST
LOCATOR=IO91WJ
AGWPORT=$agw_port
APPLICATIONS=BBS
BBSCALL=N0BBS
BBSALIAS=BBS

PORT
 ID=Telnet
 DRIVER=Telnet
 CONFIG
 TCPPORT=$telnet_port
 HTTPPORT=$http_port
 NETROMPORT=$netrom_port
 FBBPORT=$fbb_port
 APIPORT=$api_port
 MAXSESSIONS=10
 USER=test,test,N0CALL,,SYSOP
 USER=user,user,N0USER,,
ENDPORT

PORT
 ID=AXIP
 DRIVER=BPQAXIP
 CONFIG
 UDP $axip_port
ENDPORT
"""
)


def pick_free_port() -> int:
    """Bind to a kernel-assigned port on loopback, then close — return the port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class LinbpqInstance:
    """A linbpq subprocess running in an isolated working directory.

    Caller is responsible for start() / stop(); the pytest fixture wraps that.
    """

    def __init__(
        self,
        work_dir: Path,
        config_template: Template = DEFAULT_CONFIG,
        extra_args: tuple[str, ...] = (),
    ):
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.config_template = config_template
        self.extra_args = tuple(extra_args)
        self.telnet_port = pick_free_port()
        self.http_port = pick_free_port()
        self.netrom_port = pick_free_port()
        self.fbb_port = pick_free_port()
        self.api_port = pick_free_port()
        self.agw_port = pick_free_port()
        self.axip_port = pick_free_port()
        self.proc: subprocess.Popen | None = None
        self.stdout_path = self.work_dir / "linbpq.stdout.log"

    @property
    def config_path(self) -> Path:
        return self.work_dir / "bpq32.cfg"

    def render_config(self) -> str:
        return self.config_template.substitute(
            telnet_port=self.telnet_port,
            http_port=self.http_port,
            netrom_port=self.netrom_port,
            fbb_port=self.fbb_port,
            api_port=self.api_port,
            agw_port=self.agw_port,
            axip_port=self.axip_port,
        )

    def start(self, ready_timeout: float = 10.0) -> None:
        self.config_path.write_text(self.render_config())

        # Copy the repo's HTML/ template directory into the work
        # dir so GetTemplateFromFile (HTMLCommonCode.c) resolves
        # the extracted templates.  Without this, every web-UI
        # response degrades to "File is missing" stubs.
        repo_html = Path(LINBPQ_BIN).resolve().parent / "HTML"
        if repo_html.is_dir():
            target = self.work_dir / "HTML"
            target.mkdir(exist_ok=True)
            for src in repo_html.iterdir():
                if src.is_file():
                    (target / src.name).write_bytes(src.read_bytes())

        log_fh = self.stdout_path.open("wb")
        self.proc = subprocess.Popen(
            [LINBPQ_BIN, *self.extra_args],
            cwd=self.work_dir,
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
        )
        self._wait_for_ready(ready_timeout)

    def _wait_for_ready(self, timeout: float) -> None:
        deadline = time.monotonic() + timeout
        last_err: Exception | None = None
        while time.monotonic() < deadline:
            if self.proc and self.proc.poll() is not None:
                raise RuntimeError(
                    f"linbpq exited prematurely (rc={self.proc.returncode}); "
                    f"see {self.stdout_path}"
                )
            try:
                with socket.create_connection(
                    ("127.0.0.1", self.telnet_port), timeout=0.5
                ):
                    return
            except OSError as exc:
                last_err = exc
                time.sleep(0.1)
        raise TimeoutError(
            f"linbpq telnet port {self.telnet_port} did not open within "
            f"{timeout}s (last error: {last_err}); see {self.stdout_path}"
        )

    def stop(self) -> None:
        if not self.proc:
            return
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
        self.proc = None

    def __enter__(self) -> "LinbpqInstance":
        self.start()
        return self

    def __exit__(self, *_exc) -> None:
        self.stop()
