#!/usr/bin/env python3
"""LinBPQ AX.25 link-layer sequence faults: a self-contained reproduction.

This script is the far end of an AX.25 link (N0TST) and also LinBPQ's
KISS-over-TCP TNC, so one LinBPQ (N0BPQ) and Python 3 (standard
library only) are all it needs. No radio, no other software.

    python3 l2_repro.py /path/to/linbpq            # all three
    python3 l2_repro.py /path/to/linbpq dup        # or just one

Each scenario starts a fresh LinBPQ in a temporary directory, prints
every frame both ways, and ends with PASS (what AX.25 requires) or
FAIL. The exit status is the number of FAILs.

  dup      Repeated I frames (a retransmission that crossed our ack)
           are kept as future frames: LinBPQ sends SREJ for a frame
           that was never sent, then delivers the stale frames as new
           data when the sequence numbers come round again.
  badnr    One frame whose N(R) acks frames LinBPQ never sent: LinBPQ
           goes silent (no FRMR, no reset), ignores every later frame,
           polls and finally disconnects.
  counter  A burst of frames that bring no new acknowledgement:
           LinBPQ's "Too many repeats of same I frame" check counts
           each one and disconnects a healthy link.

The pytest suite (tests/integration/test_l2_sequence_errors.py) runs
the same scenarios. See packet-net/dapps#425.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

FEND, FESC, TFEND, TFESC = 0xC0, 0xDB, 0xDC, 0xDD
ME, NODE = ("N0TST", 0), ("N0BPQ", 0)

# SREJ/REJ/RR/RNR and U-frame control values (P/F bit masked off).
RR, RNR, REJ, SREJ = 0x01, 0x05, 0x09, 0x0D
SABM, UA, DISC, DM, FRMR, XID = 0x2F, 0x63, 0x43, 0x0F, 0x87, 0xAF
PF = 0x10

CONFIG = """\
SIMPLE=1
NODECALL=N0BPQ
NODEALIAS=BPQ
LOCATOR=NONE
IDINTERVAL=0
BTINTERVAL=0

PORT
 ID=Radio
 TYPE=ASYNC
 PROTOCOL=KISS
 IPADDR=127.0.0.1
 TCPPORT={kiss_port}
 CHANNEL=A
 SPEED=1200
 FRACK=7000
 RESPTIME=1000
 RETRIES=4
 MAXFRAME=4
 PACLEN=120
ENDPORT
"""

# XID as LinBPQ itself sends it: half duplex, mod 8, REJ, SREJ, SREJ multi.
XID_INFO = bytes([0x82, 0x80, 0x00, 0x10, 0x02, 0x02, 0x00, 0x21, 0x03,
                  0x03, 0x22, 0xA4, 0x86, 0x06, 0x02, 0x08, 0x00, 0x08,
                  0x01, 0x07])


def _addr(call, ssid, bit7, last):
    b = bytes((ord(c) << 1) for c in call.ljust(6))
    return b + bytes([0x60 | (ssid << 1) | (0x80 if bit7 else 0) | (1 if last else 0)])


def frame(ctl, info=b"", cmd=True, pid=None):
    a = _addr(*NODE, cmd, False) + _addr(*ME, not cmd, True)
    return a + bytes([ctl]) + (bytes([pid]) if pid is not None else b"") + info


def I(ns, nr, data, p=False):
    return frame((nr << 5) | (PF if p else 0) | (ns << 1), data, cmd=True, pid=0xF0)


def S(kind, nr, cmd=True, pf=False):
    return frame((nr << 5) | (PF if pf else 0) | kind, cmd=cmd)


def U(kind, cmd=True, pf=True, info=b""):
    return frame(kind | (PF if pf else 0), info, cmd=cmd)


def kiss(body):
    out = bytearray([FEND, 0x00])
    for b in body:
        out += {FEND: bytes([FESC, TFEND]), FESC: bytes([FESC, TFESC])}.get(b, bytes([b]))
    out.append(FEND)
    return bytes(out)


class Rx:
    """A decoded frame from LinBPQ to us."""

    def __init__(self, body):
        i = 14
        while not (body[i - 1] & 1):
            i += 7
        self.body = body
        self.cmd = bool(body[6] & 0x80)
        self.ctl = body[i]
        self.info = body[i + 1:]

    @property
    def is_i(self):
        return self.ctl & 1 == 0

    @property
    def is_s(self):
        return self.ctl & 3 == 1

    @property
    def kind(self):
        """RR/RNR/REJ/SREJ value for S frames, U value for U frames."""
        if self.is_s:
            return self.ctl & 0x0F
        return self.ctl & ~PF & 0xFF

    @property
    def pf(self):
        return bool(self.ctl & PF)

    @property
    def nr(self):
        return self.ctl >> 5

    @property
    def ns(self):
        return (self.ctl >> 1) & 7


def describe(body):
    def call(b):
        c = "".join(chr(x >> 1) for x in b[:6]).strip()
        s = (b[6] >> 1) & 15
        return c + (f"-{s}" if s else "")

    f = Rx(body)
    cr = "C" if f.cmd else "R"
    if f.is_i:
        k = f"I {cr}{' P' if f.pf else ''} S{f.ns} R{f.nr} {f.info[1:]!r}"
    elif f.is_s:
        name = {RR: "RR", RNR: "RNR", REJ: "REJ", SREJ: "SREJ"}[f.kind]
        k = f"{name} {cr}{(' P' if f.cmd else ' F') if f.pf else ''} R{f.nr}"
    else:
        name = {SABM: "SABM", UA: "UA", DISC: "DISC", DM: "DM", FRMR: "FRMR",
                XID: "XID", 0x03: "UI", 0x6F: "SABME"}.get(f.kind, f"U{f.kind:02x}")
        k = f"{name} {cr}{' P/F' if f.pf else ''}"
    return f"{call(body[7:14])}>{call(body[0:7])} <{k}>"


class Link:
    """KISS-over-TCP server that LinBPQ connects to as its TNC."""

    def __init__(self, log):
        self.log = log
        self.srv = socket.socket()
        self.srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.srv.bind(("127.0.0.1", 0))
        self.srv.listen(1)
        self.port = self.srv.getsockname()[1]
        self.s = None
        self.rx = []
        self.lock = threading.Lock()

    def accept(self, timeout):
        self.srv.settimeout(timeout)
        self.s, _ = self.srv.accept()
        self.s.settimeout(None)
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self):
        buf, esc = bytearray(), False
        while True:
            try:
                d = self.s.recv(4096)
            except OSError:
                return
            if not d:
                return
            for b in d:
                if b == FEND:
                    # Data frames on KISS port 0, addressed to us, from the node.
                    if len(buf) > 15 and buf[0] == 0:
                        body = bytes(buf[1:])
                        if body[0:6] == bytes(ord(c) << 1 for c in ME[0].ljust(6)):
                            with self.lock:
                                self.rx.append(Rx(body))
                            self.log(f"RX  {describe(body)}")
                    buf = bytearray()
                elif b == FESC:
                    esc = True
                else:
                    if esc:
                        b = {TFEND: FEND, TFESC: FESC}.get(b, b)
                        esc = False
                    buf.append(b)

    def send(self, body, note=""):
        self.log(f"TX  {describe(body)}{'   # ' + note if note else ''}")
        self.s.sendall(kiss(body))

    def wait_for(self, pred, timeout):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            with self.lock:
                for f in self.rx:
                    if pred(f):
                        self.rx.remove(f)
                        return f
            time.sleep(0.05)
        return None

    def take_all(self):
        with self.lock:
            out, self.rx = self.rx, []
        return out

    def close(self):
        for s in (self.s, self.srv):
            try:
                if s:
                    s.close()
            except OSError:
                pass


class Result:
    def __init__(self, name):
        self.name = name
        self.lines = []
        self.failures = []
        self.t0 = time.monotonic()

    def log(self, line):
        self.lines.append(f"{time.monotonic() - self.t0:7.2f}  {line}")

    def fail(self, why):
        self.failures.append(why)
        self.log(f"*** {why}")

    @property
    def ok(self):
        return not self.failures

    def report(self):
        head = f"=== {self.name}: {'PASS' if self.ok else 'FAIL'}"
        return "\n".join([head, *self.lines, head])


def _connect(link, r, xid):
    if xid:
        link.send(U(XID, info=XID_INFO), "XID: offer AX.25 2.2 with SREJ, as LinBPQ does")
        if not link.wait_for(lambda f: f.kind == XID, 5):
            raise RuntimeError("no XID response")
    link.send(U(SABM))
    if not link.wait_for(lambda f: f.kind == UA, 5):
        raise RuntimeError("no UA to SABM")
    time.sleep(3)  # let any connect text arrive
    link.take_all()


def scenario_dup(link, r):
    """AX.25 2.3 draft 4.4.2, 6.4.4.1, 6.4.4.2: an N(S) outside the receive
    window is a duplicate; discard it, raise no REJ/SREJ, answer only a poll."""
    _connect(link, r, xid=True)
    r.log("--- four new frames S0..S3, P on S3: LinBPQ acks R4")
    for ns, d in enumerate(b"abcd"):
        link.send(I(ns, 0, bytes([d]), p=(ns == 3)))
    time.sleep(3)
    link.take_all()
    r.log("--- S2 and S3 again, P=0: repeats that crossed the ack. Expected: discarded, no REJ or SREJ")
    link.send(I(2, 0, b"c"), "repeat")
    link.send(I(3, 0, b"d"), "repeat")
    time.sleep(4)
    link.send(S(RR, 0, cmd=True, pf=True), "poll: expected RR F R4")
    time.sleep(4)
    for f in link.take_all():
        if f.is_s and f.kind in (REJ, SREJ):
            r.fail(f"{describe(f.body)} after repeated frames: asks for frame {f.nr}, which was never sent")
        elif f.is_s and f.pf and f.nr != 4:
            r.fail(f"poll answered with N(R) {f.nr}, expected 4")
    r.log("--- next cycle: new frames S4..S7, S0, S1 (P=0). S2 and S3 are never sent again")
    for i, ns in enumerate([4, 5, 6, 7, 0, 1]):
        link.send(I(ns, 0, bytes([ord("e") + i])), "new")
    time.sleep(4)
    link.take_all()
    link.send(S(RR, 0, cmd=True, pf=True), "poll: we have sent up to S1, so expected N(R) 2")
    f = link.wait_for(lambda f: f.is_s and f.pf and not f.cmd, 5)
    if f is None:
        r.fail("no answer to the poll")
    elif f.nr != 2:
        r.fail(f"N(R) {f.nr}, expected 2: LinBPQ has delivered the old S2 and S3 as new data")


def scenario_badnr(link, r):
    """AX.25 2.3 draft 4.3.3.9, 6.5 and figure C4.7 (N(r) Error Recovery):
    an invalid N(R) resets the link with SABM; the station must not go silent."""
    _connect(link, r, xid=False)
    r.log("--- ask the node for something so it sends us I frames")
    link.send(I(0, 0, b"VERSION\r"))
    first = link.wait_for(lambda f: f.is_i, 10)
    if first is None:
        raise RuntimeError("LinBPQ sent no I frame")
    time.sleep(2)
    vs = (first.ns + 1 + sum(1 for f in link.take_all() if f.is_i)) & 7
    bad = (vs + 2) & 7
    link.send(S(RR, bad, cmd=False), f"N(R) {bad} acks frames LinBPQ never sent (its V(S) is {vs})")
    time.sleep(1)
    r.log("--- valid frames from here on. Expected: LinBPQ resets the link (SABM) or sends FRMR")
    link.send(I(1, vs, b"VERSION\r", p=True), "valid I frame with poll, acks everything")
    end = time.monotonic() + 45
    answered = False
    while time.monotonic() < end:
        f = link.wait_for(lambda f: True, 1)
        if f is None:
            continue
        if f.kind in (SABM, FRMR) and not f.is_s and not f.is_i:
            if f.kind == SABM:
                link.send(U(UA, cmd=False), "UA: link reset as the spec says")
                time.sleep(2)
                link.take_all()
                link.send(S(RR, 0, cmd=True, pf=True), "poll: the reset link should answer")
                if not link.wait_for(lambda f: f.is_s and f.pf and not f.cmd, 5):
                    r.fail("no answer to a poll after the link reset")
            return
        if f.kind == DISC and not f.is_s and not f.is_i:
            link.send(U(UA, cmd=False))
            r.fail("LinBPQ ignored every valid frame after one bad N(R), then disconnected the link"
                   + ("" if answered else " (it never answered our poll)"))
            return
        if f.is_s and f.cmd and f.pf:
            link.send(S(RR, vs, cmd=False, pf=True), "answer its poll, valid N(R)")
        if f.is_s and not f.cmd and f.pf:
            answered = True
    r.fail("no SABM, FRMR or DISC within 45 s of the bad N(R)")


def scenario_counter(link, r):
    """A frame that brings no new acknowledgement is normal (2.3 draft 6.4.6);
    the link is reset only after N2 unanswered polls (6.4.11)."""
    _connect(link, r, xid=False)
    r.log("--- ask the node for something so it has I frames outstanding")
    link.send(I(0, 0, b"VERSION\r"))
    first = link.wait_for(lambda f: f.is_i, 10)
    if first is None:
        raise RuntimeError("LinBPQ sent no I frame")
    time.sleep(0.5)
    r.log("--- one long transmission of ours, built before we heard its frames: 7 new I frames,"
          " each with the old N(R). Expected: LinBPQ acks them; the link stays up")
    for ns in range(1, 8):
        link.send(I(ns, first.ns, b"a"), "new data, stale N(R)")
    time.sleep(2)
    got = link.take_all()
    if any(f.kind == DISC and not f.is_s and not f.is_i for f in got):
        link.send(U(UA, cmd=False))
        r.fail("LinBPQ disconnected a healthy link (\"Too many repeats of same I frame\")")
        return
    vs = (first.ns + 1 + sum(1 for f in got if f.is_i)) & 7
    link.send(S(RR, vs, cmd=True, pf=True), "now ack everything it sent, and poll")
    end = time.monotonic() + 10
    while time.monotonic() < end:
        f = link.wait_for(lambda f: True, 1)
        if f is None:
            continue
        if f.kind == DISC and not f.is_s and not f.is_i:
            link.send(U(UA, cmd=False))
            r.fail("LinBPQ disconnected a healthy link (\"Too many repeats of same I frame\")")
            return
        if f.is_s and not f.cmd and f.pf:
            return
    r.fail("no answer to the poll")


def scenario_srejloop(link, r):
    """Regression guard for the counter move (not an upstream fault): a 2.2
    peer that answers every poll, the resent I(P) included, with SREJ F for
    the same frame must still be disconnected after N2 rounds, not held forever."""
    _connect(link, r, xid=True)
    link.send(I(0, 0, b"VERSION\r"))
    first = link.wait_for(lambda f: f.is_i, 10)
    if first is None:
        raise RuntimeError("LinBPQ sent no I frame")
    r.log("--- every poll, I(P) resends included, answered SREJ F for the same frame."
          " Expected: DISC (\"Too many repeats of same I frame\")")
    end = time.monotonic() + 60
    while time.monotonic() < end:
        f = link.wait_for(lambda f: True, 1)
        if f is None:
            continue
        if f.kind == DISC and not f.is_s and not f.is_i:
            link.send(U(UA, cmd=False))
            return
        if f.cmd and f.pf and (f.is_s or f.is_i):
            link.send(S(SREJ, first.ns, cmd=False, pf=True), "asks for the same frame again")
    r.fail("no DISC within 60 s: a peer stuck on one SREJ holds the link forever")


SCENARIOS = {"dup": scenario_dup, "badnr": scenario_badnr, "counter": scenario_counter,
             "srejloop": scenario_srejloop}
# The three upstream faults; srejloop runs only by name or from pytest.
DEFAULT = ["dup", "badnr", "counter"]


def run_scenario(name, linbpq, work_dir=None):
    """Start a fresh LinBPQ, play one scenario against it, return a Result."""
    r = Result(name)
    work = Path(work_dir or tempfile.mkdtemp(prefix=f"l2repro-{name}-"))
    work.mkdir(parents=True, exist_ok=True)
    (work / "logs").mkdir(exist_ok=True)
    link = Link(r.log)
    (work / "bpq32.cfg").write_text(CONFIG.format(kiss_port=link.port))
    out = open(work / "linbpq.out", "wb")
    exe = os.path.abspath(linbpq if os.sep in linbpq else shutil.which(linbpq) or linbpq)
    proc = subprocess.Popen([exe], cwd=work, stdout=out,
                            stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
    try:
        link.accept(30)
        r.log(f"LinBPQ connected to our KISS port {link.port}")
        SCENARIOS[name](link, r)
    except Exception as e:  # setup trouble, not the fault under test
        r.fail(f"scenario could not run: {e!r}; see {work}")
    finally:
        link.close()
        proc.terminate()
        try:
            proc.wait(5)
        except subprocess.TimeoutExpired:
            proc.kill()
        out.close()
    return r


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    names = argv[2:] or DEFAULT
    results = []
    for n in names:
        r = run_scenario(n, argv[1])
        print(r.report(), flush=True)
        print()
        results.append(r)
    print("SUMMARY: " + ", ".join(f"{r.name} {'PASS' if r.ok else 'FAIL'}" for r in results))
    return sum(not r.ok for r in results)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
