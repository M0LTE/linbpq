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

import shutil
import subprocess
import time
from pathlib import Path
from string import Template

import pytest

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


# LD_PRELOAD shim that holds the creating thread for 2 ms after every
# pthread_create, so the new thread runs first.  A busy scheduler does
# that now and then on its own; the shim makes it happen every time.
CHILD_FIRST_SHIM = r"""
#define _GNU_SOURCE
#include <dlfcn.h>
#include <pthread.h>
#include <unistd.h>

int pthread_create(pthread_t *t, const pthread_attr_t *a,
                   void *(*f)(void *), void *arg)
{
    static int (*real)(pthread_t *, const pthread_attr_t *,
                       void *(*)(void *), void *);
    int r;

    if (!real)
        real = dlsym(RTLD_NEXT, "pthread_create");
    r = real(t, a, f, arg);
    usleep(2000);
    return r;
}
"""


def test_kiss_tcp_client_survives_connect_when_its_thread_runs_first(
    tmp_path: Path, monkeypatch
):
    """ASYINIT starts ConnecttoTCPThread, which copies ASY->Portvector
    as its first statement.  Portvector used to be set only after the
    thread had started, so if the thread ran first it kept NULL and
    segfaulted on ``KISS->PORT.FREQ`` once it connected, 10 s after
    start-up.
    """
    gcc = shutil.which("gcc")
    if gcc is None:
        pytest.skip("needs gcc to build the scheduling shim")

    shim_src = tmp_path / "child_first.c"
    shim_src.write_text(CHILD_FIRST_SHIM)
    shim = tmp_path / "child_first.so"
    subprocess.run(
        [gcc, "-shared", "-fPIC", "-o", str(shim), str(shim_src), "-ldl"],
        check=True,
    )
    monkeypatch.setenv("LD_PRELOAD", str(shim))

    with kiss_tcp_server() as server:
        class _Config(Template):
            def substitute(self, **kw):
                return Template.substitute(
                    self, kiss_tcp_port=server.port, **kw
                )

        cfg = _Config(KISS_TCP_CLIENT_CONFIG.template)

        with LinbpqInstance(tmp_path / "node", config_template=cfg) as inst:
            assert server.wait_for_client(timeout=15.0), (
                "linbpq did not connect to the KISS-TCP server within 15s"
            )
            # The crash came straight after the connect; give it time.
            time.sleep(2.0)
            assert inst.proc.poll() is None, (
                f"linbpq exited (rc={inst.proc.returncode}) just after "
                f"connecting; see {inst.stdout_path}"
            )
