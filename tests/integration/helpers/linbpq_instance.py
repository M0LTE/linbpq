"""Spawn / control a linbpq.bin process for integration tests."""

from __future__ import annotations

import os
import socket
import subprocess
import time
from pathlib import Path
from string import Template

LINBPQ_BIN = os.environ.get("LINBPQ_BIN", "linbpq.bin")

# A bpq32.cfg that boots cleanly with the standard set of TCP-only
# interfaces enabled, no radio, all on loopback.  See docs/plan.md.
#
# Telnet/HTTP/NETROM/FBB/API all share one DRIVER=Telnet PORT block
# (TelnetV6.c hands them the same CONFIG section).  AGW is a separate
# global keyword.  KISS-TCP and AX/IP-UDP need their own PORT blocks
# and are added in later phases.
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
"""
)

# Backwards-compat alias for any earlier tests that imported MINIMAL_CONFIG.
MINIMAL_CONFIG = DEFAULT_CONFIG


def pick_free_port() -> int:
    """Bind to a kernel-assigned port on loopback, then close — return the port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class LinbpqInstance:
    """A linbpq.bin subprocess running in an isolated working directory.

    Caller is responsible for start() / stop(); the pytest fixture wraps that.
    """

    def __init__(self, work_dir: Path, config_template: Template = DEFAULT_CONFIG):
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.config_template = config_template
        self.telnet_port = pick_free_port()
        self.http_port = pick_free_port()
        self.netrom_port = pick_free_port()
        self.fbb_port = pick_free_port()
        self.api_port = pick_free_port()
        self.agw_port = pick_free_port()
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
        )

    def start(self, ready_timeout: float = 10.0) -> None:
        self.config_path.write_text(self.render_config())

        log_fh = self.stdout_path.open("wb")
        self.proc = subprocess.Popen(
            [LINBPQ_BIN],
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
