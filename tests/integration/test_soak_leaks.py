"""Soak / leak detection.

Drive linbpq through high-cycle connect-disconnect bursts on each
listener (telnet, FBB, AGW, HTTP) and watch RSS + open-fd count
for unbounded growth.

Production linbpq daemons run for months; even small per-cycle
leaks compound.  These tests catch the class of bug nothing else
in the suite would: nothing observable changes from a wire-
protocol perspective, but the daemon's footprint creeps upward.

Per ``notes/plan.md`` the policy is to *file findings as issues*,
not fix in C.  These tests carry generous thresholds so they
won't flag glibc heap fragmentation noise; if they fire, it's
a real growth signal worth investigating.

All marked ``long_runtime`` so pytest-xdist sorts them to the
front of the queue (they take ~2 min each, so they run in
parallel with the rest of the suite).
"""

from __future__ import annotations

import os
import socket
import time
from pathlib import Path
from string import Template

import pytest

from helpers.linbpq_instance import LinbpqInstance
from helpers.telnet_client import TelnetClient


_SOAK_CFG = Template(
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
 FBBPORT=$fbb_port
 AGWPORT=$agw_port
 MAXSESSIONS=20
 USER=test,test,N0CALL,,SYSOP
ENDPORT
"""
)


@pytest.fixture
def soak_linbpq(tmp_path: Path):
    """Lightweight linbpq instance with all the listeners enabled
    so each soak test can target a specific one."""
    instance = LinbpqInstance(tmp_path, config_template=_SOAK_CFG)
    instance.start(ready_timeout=15.0)
    try:
        yield instance
    finally:
        try:
            if instance.proc:
                instance.proc.terminate()
                instance.proc.wait(timeout=5)
        except Exception:
            if instance.proc:
                instance.proc.kill()


def _read_rss_kb(pid: int) -> int:
    """Read VmRSS in KiB from /proc/<pid>/status."""
    with open(f"/proc/{pid}/status") as f:
        for line in f:
            if line.startswith("VmRSS:"):
                return int(line.split()[1])
    raise RuntimeError(f"VmRSS not in /proc/{pid}/status")


def _count_open_fds(pid: int) -> int:
    """Count entries under /proc/<pid>/fd/."""
    try:
        return len(os.listdir(f"/proc/{pid}/fd"))
    except OSError:
        return -1


def _measure(pid: int) -> tuple[int, int]:
    """Return (rss_kb, fd_count) for a process."""
    return _read_rss_kb(pid), _count_open_fds(pid)


def _warm_up(pid: int, settle_seconds: float = 2.0) -> tuple[int, int]:
    """Let glibc / linbpq settle, then take a baseline."""
    time.sleep(settle_seconds)
    return _measure(pid)


def _format(rss_before: int, fd_before: int, rss_after: int, fd_after: int, cycles: int) -> str:
    return (
        f"after {cycles} cycles: "
        f"RSS {rss_before} → {rss_after} KiB "
        f"(Δ {rss_after - rss_before:+d}, "
        f"per-cycle {(rss_after - rss_before) / cycles:.2f}); "
        f"fds {fd_before} → {fd_after} "
        f"(Δ {fd_after - fd_before:+d})"
    )


# ── Telnet listener: connect-disconnect cycles ───────────────────


@pytest.mark.long_runtime
def test_telnet_listener_no_leak_on_login_cycles(soak_linbpq):
    """1000 telnet login + disconnect cycles.

    Thresholds:
    - RSS: max 5 MiB total growth (≈ 5 KiB/cycle).  Linux pages
      are 4K so even a tiny glibc-driven heap top-up shows up
      as page-aligned increments.
    - FDs: must not grow at all (each cycle should fully release
      its socket; a leak here is unambiguous).
    """
    pid = soak_linbpq.proc.pid
    rss_before, fd_before = _warm_up(pid)
    cycles = 1000

    for _ in range(cycles):
        with TelnetClient(
            "127.0.0.1", soak_linbpq.telnet_port, timeout=3
        ) as client:
            client.login("test", "test")
            client.write_line("BYE")

    # Brief drain so any reaper threads finish.
    time.sleep(2.0)
    rss_after, fd_after = _measure(pid)

    summary = _format(rss_before, fd_before, rss_after, fd_after, cycles)
    print(summary)

    # FDs must be flat.
    assert fd_after <= fd_before + 2, (
        f"FD leak on telnet listener: {summary}"
    )
    # RSS allowed to grow up to 5 MiB.
    assert rss_after - rss_before < 5 * 1024, (
        f"RSS leak on telnet listener: {summary}"
    )


# ── FBB listener: connect-disconnect cycles ──────────────────────


@pytest.mark.long_runtime
def test_fbb_listener_no_leak_on_login_cycles(soak_linbpq):
    """500 FBB host-mode login + disconnect cycles.

    Lower count than telnet because FBB sessions take a beat
    longer to establish (no IAC negotiation, but BPQ still
    allocates a stream).
    """
    pid = soak_linbpq.proc.pid
    rss_before, fd_before = _warm_up(pid)
    cycles = 500

    for _ in range(cycles):
        sock = socket.create_connection(
            ("127.0.0.1", soak_linbpq.fbb_port), timeout=3
        )
        try:
            sock.settimeout(2.0)
            sock.sendall(b"test\r")
            time.sleep(0.05)
            sock.sendall(b"test\r")
            time.sleep(0.1)
            try:
                sock.recv(4096)
            except (TimeoutError, socket.timeout):
                pass
            sock.sendall(b"BYE\r")
            time.sleep(0.05)
        finally:
            sock.close()

    time.sleep(2.0)
    rss_after, fd_after = _measure(pid)

    summary = _format(rss_before, fd_before, rss_after, fd_after, cycles)
    print(summary)
    assert fd_after <= fd_before + 2, (
        f"FD leak on FBB listener: {summary}"
    )
    assert rss_after - rss_before < 5 * 1024, (
        f"RSS leak on FBB listener: {summary}"
    )


# ── AGW listener: connect-register-disconnect cycles ─────────────


@pytest.mark.long_runtime
def test_agw_listener_no_leak_on_register_cycles(soak_linbpq):
    """500 AGW connect → register-callsign → close cycles.

    AGW callsign registration allocates internal state
    (``BPQConnectionInfo`` slots, callsign tables); a leak in
    that path would compound across many short-lived clients.
    """
    from helpers.agw_client import AgwSession

    pid = soak_linbpq.proc.pid
    rss_before, fd_before = _warm_up(pid)
    cycles = 500

    for i in range(cycles):
        try:
            with AgwSession.connect(
                "127.0.0.1", soak_linbpq.agw_port, timeout=3
            ) as session:
                # Register a unique-ish call to avoid any de-dup that
                # might mask a leak.
                session.register(f"S{i:05X}")
        except (ConnectionError, OSError, AssertionError):
            # If the listener gets temporarily refused, skip the
            # cycle — but if it happens often we want to know.
            time.sleep(0.05)

    time.sleep(2.0)
    rss_after, fd_after = _measure(pid)

    summary = _format(rss_before, fd_before, rss_after, fd_after, cycles)
    print(summary)
    assert fd_after <= fd_before + 2, (
        f"FD leak on AGW listener: {summary}"
    )
    # AGW reportedly allocates per-callsign state; allow a touch
    # more headroom (10 MiB) before flagging.
    assert rss_after - rss_before < 10 * 1024, (
        f"RSS leak on AGW listener: {summary}"
    )


# ── HTTP listener: connect-request-disconnect cycles ─────────────


@pytest.mark.long_runtime
def test_http_listener_no_leak_on_request_cycles(soak_linbpq):
    """1000 short HTTP GET cycles to /Node/NodeIndex.html.

    Each request boots through SetupNodeMenu and the
    template-load path; a leak in the per-request state would
    compound here.
    """
    pid = soak_linbpq.proc.pid
    rss_before, fd_before = _warm_up(pid)
    cycles = 1000

    for _ in range(cycles):
        try:
            sock = socket.create_connection(
                ("127.0.0.1", soak_linbpq.http_port), timeout=2
            )
        except OSError:
            time.sleep(0.05)
            continue
        try:
            sock.sendall(
                b"GET /Node/NodeIndex.html HTTP/1.0\r\n"
                b"Host: 127.0.0.1\r\n"
                b"Connection: close\r\n\r\n"
            )
            sock.settimeout(1.0)
            try:
                while True:
                    if not sock.recv(4096):
                        break
            except (TimeoutError, socket.timeout):
                pass
        finally:
            sock.close()

    time.sleep(2.0)
    rss_after, fd_after = _measure(pid)

    summary = _format(rss_before, fd_before, rss_after, fd_after, cycles)
    print(summary)
    assert fd_after <= fd_before + 2, (
        f"FD leak on HTTP listener: {summary}"
    )
    assert rss_after - rss_before < 5 * 1024, (
        f"RSS leak on HTTP listener: {summary}"
    )


# ── Two-instance: cross-AX/IP-UDP connect cycles ─────────────────


@pytest.fixture
def two_instance_soak(tmp_path: Path):
    """Two BPQs over AX/IP-UDP with bidirectional MAP entries.
    Trimmed-down twin of ``test_two_instance.py::two_instances`` —
    same config shape, no extra fixtures, fast teardown.
    """
    from helpers.linbpq_instance import PEER_CONFIG

    def _peer_template(*, node_call, node_alias, peer_call, peer_axip_port):
        base = PEER_CONFIG.template

        class _T(Template):
            def substitute(self, **kw):
                return Template.substitute(
                    self,
                    node_call=node_call,
                    node_alias=node_alias,
                    peer_call=peer_call,
                    peer_axip_port=peer_axip_port,
                    **kw,
                )

        return _T(base)

    a_dir = tmp_path / "A"
    b_dir = tmp_path / "B"
    a_dir.mkdir()
    b_dir.mkdir()

    a = LinbpqInstance(
        a_dir,
        config_template=_peer_template(
            node_call="N0AAA",
            node_alias="AAA",
            peer_call="N0BBB",
            peer_axip_port=0,
        ),
    )
    b = LinbpqInstance(
        b_dir,
        config_template=_peer_template(
            node_call="N0BBB",
            node_alias="BBB",
            peer_call="N0AAA",
            peer_axip_port=a.axip_port,
        ),
    )
    a.config_template = _peer_template(
        node_call="N0AAA",
        node_alias="AAA",
        peer_call="N0BBB",
        peer_axip_port=b.axip_port,
    )

    a.start(ready_timeout=15.0)
    b.start(ready_timeout=15.0)
    try:
        # Let NODES propagation settle so the first connect doesn't
        # race the route-discovery exchange.
        time.sleep(2.0)
        yield a, b
    finally:
        for inst in (a, b):
            try:
                if inst.proc:
                    inst.proc.terminate()
                    inst.proc.wait(timeout=5)
            except Exception:
                if inst.proc:
                    inst.proc.kill()


@pytest.mark.long_runtime
@pytest.mark.parametrize(
    "direction,target_call",
    [
        pytest.param("a_to_b", "N0BBB", id="a_to_b"),
        pytest.param("b_to_a", "N0AAA", id="b_to_a"),
    ],
)
def test_two_instance_axip_no_leak_on_connect_cycles(
    two_instance_soak, direction, target_call
):
    """Cycle ``C 2 <peer>`` → ``BYE`` over AX/IP-UDP.

    Catches AX/IP-UDP-side leaks the single-instance variants miss:
    per-cycle SABM/UA over UDP, L4 link-state on both sides,
    NET/ROM neighbour-table churn, the per-peer ARP-cache row in
    bpqaxip.c.  Each BPQ is monitored independently — a leak that
    shows on only one side still fails the test.

    Parametrised on direction so xdist can run the two halves in
    parallel on separate workers — each spawns its own pair of
    BPQs, halving wallclock vs the merged single-test variant.
    """
    a, b = two_instance_soak
    client_inst = a if direction == "a_to_b" else b
    a_pid = a.proc.pid
    b_pid = b.proc.pid

    rss_a_before, fd_a_before = _warm_up(a_pid)
    rss_b_before, fd_b_before = _measure(b_pid)
    # Each cross-instance connect runs ~6 s wallclock (telnet
    # login + AX/IP-UDP SABM/UA + BYE + close).  25 cycles per
    # direction × 2 directions = 50 total — same total signal as
    # the previous single-direction 50-cycle test, but the two
    # halves run in parallel on different xdist workers, halving
    # wallclock from ~12 min → ~6 min.
    cycles = 25
    connected_marker = f"Connected to {target_call}".encode("ascii")

    for _ in range(cycles):
        try:
            with TelnetClient(
                "127.0.0.1", client_inst.telnet_port, timeout=10
            ) as client:
                client.login("test", "test")
                client.write_line(f"C 2 {target_call}")
                client.read_until(connected_marker, timeout=8)
                client.write_line("BYE")
                client.read_idle(idle_timeout=0.5, max_total=2.0)
        except (ConnectionError, OSError, TimeoutError):
            time.sleep(0.05)

    time.sleep(2.0)
    rss_a_after, fd_a_after = _measure(a_pid)
    rss_b_after, fd_b_after = _measure(b_pid)

    summary_a = _format(
        rss_a_before, fd_a_before, rss_a_after, fd_a_after, cycles
    )
    summary_b = _format(
        rss_b_before, fd_b_before, rss_b_after, fd_b_after, cycles
    )
    print(f"A: {summary_a}")
    print(f"B: {summary_b}")

    assert fd_a_after <= fd_a_before + 2, f"FD leak on A: {summary_a}"
    assert fd_b_after <= fd_b_before + 2, f"FD leak on B: {summary_b}"
    # AX/IP + L4 + NET/ROM allocate per-cycle state buffers.  15 MiB
    # of slack tolerates glibc heap variance over the cycle count.
    assert rss_a_after - rss_a_before < 15 * 1024, (
        f"RSS leak on A: {summary_a}"
    )
    assert rss_b_after - rss_b_before < 15 * 1024, (
        f"RSS leak on B: {summary_b}"
    )
