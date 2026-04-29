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
    from helpers.agw_client import AgwClient, AgwFrame

    pid = soak_linbpq.proc.pid
    rss_before, fd_before = _warm_up(pid)
    cycles = 500

    for i in range(cycles):
        try:
            with AgwClient(
                "127.0.0.1", soak_linbpq.agw_port, timeout=3
            ) as client:
                # Register a unique-ish call to avoid any de-dup that
                # might mask a leak.
                client.send(
                    AgwFrame(
                        port=0,
                        data_kind=b"X",
                        pid=0,
                        callfrom=f"S{i:05X}".encode("ascii"),
                        callto=b"",
                        data=b"",
                    )
                )
                # Drain the success reply.
                client.recv()
        except (ConnectionError, OSError):
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
