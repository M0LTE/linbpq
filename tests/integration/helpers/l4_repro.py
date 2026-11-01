#!/usr/bin/env python3
"""LinBPQ NET/ROM L4: a resent fragment is 20 bytes short. A self-contained reproduction.

This script is LinBPQ's KISS-over-TCP TNC, the far end of the link (a
NET/ROM node, N0TST) and an AGW application on the LinBPQ node
(N0BPQ-6), so one LinBPQ (N0BPQ) and Python 3 (standard library only)
are all it needs. No radio, no other software.

    python3 l4_repro.py /path/to/linbpq            # both
    python3 l4_repro.py /path/to/linbpq timer      # or timer, nak

Each scenario starts a fresh LinBPQ in a temporary directory, prints
every NET/ROM frame LinBPQ sends, and ends with PASS or FAIL. The exit
status is the number of FAILs.

In both, N0TST opens a NET/ROM circuit to the application, and the
application writes 256 bytes in one AGW frame. That is more than one
NET/ROM frame carries (236), so LinBPQ sends two INFO frames: 236 bytes
with More-follows, then 20. N0TST acks them at L2 but not at L4, so
LinBPQ has to send them again from its L4 hold queue:

  timer    N0TST sends no L4 ack at all; after L4TIMEOUT (10 s here)
           LinBPQ resends both frames.
  nak      N0TST sends an INFO ACK with the NAK flag for the first
           frame; LinBPQ resends that frame straight away.

PASS: each resent frame is the frame that was sent, the same bytes and
the same More-follows flag. FAIL (6.0.26.1 and earlier): the resent
236-byte frame carries only its first 216 bytes. The other 20 are gone
for good; the far end reassembles a stream 20 bytes short with nothing
to say so.

The pytest suite (tests/integration/test_l4_fragment_resend.py) runs the
same scenarios. See packet-net/dapps#425.
"""

from __future__ import annotations

import os
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

FEND, FESC, TFEND, TFESC = 0xC0, 0xDB, 0xDC, 0xDD
RR, SABM, UA, UI = 0x01, 0x2F, 0x63, 0x03
PF = 0x10

# NET/ROM L4 opcodes and flags (the low nibble is the opcode).
CONN_REQ, CONN_ACK, INFO, INFO_ACK = 1, 2, 5, 6
NAK, MORE = 0x40, 0x20

ME, NODE, APP = "N0TST", "N0BPQ", "N0BPQ-6"
PAYLOAD = bytes(range(256))

CONFIG = """\
SIMPLE=1
NODECALL=N0BPQ
NODEALIAS=BPQ
LOCATOR=NONE
IDINTERVAL=0
BTINTERVAL=0
MINQUAL=1
L4TIMEOUT=10
L4RETRIES=3
AGWPORT={agw_port}
AGWSESSIONS=10
AGWMASK=255
APPLICATION 1,TESTAPP,,N0BPQ-6,BPQAPP,0

PORT
 ID=Link
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
 PACLEN=236
 QUALITY=200
 MINQUAL=1
ENDPORT
"""


def ax_call(call, last=False, bit7=False):
    c, _, s = call.partition("-")
    ssid = int(s or 0)
    return (bytes(ord(x) << 1 for x in c.ljust(6))
            + bytes([0x60 | (ssid << 1) | (0x80 if bit7 else 0) | (1 if last else 0)]))


def nr_call(call):
    c, _, s = call.partition("-")
    return bytes(ord(x) << 1 for x in c.ljust(6)) + bytes([0x60 | (int(s or 0) << 1)])


def dec_call(b):
    c = "".join(chr(x >> 1) for x in b[:6]).strip()
    s = (b[6] >> 1) & 15
    return f"{c}-{s}" if s else c


def frame(ctl, info=b"", cmd=True, pid=None):
    return (ax_call(NODE, bit7=cmd) + ax_call(ME, last=True, bit7=not cmd) + bytes([ctl])
            + (bytes([pid]) if pid is not None else b"") + info)


def kiss(body):
    out = bytearray([FEND, 0x00])
    for b in body:
        out += {FEND: bytes([FESC, TFEND]), FESC: bytes([FESC, TFESC])}.get(b, bytes([b]))
    out.append(FEND)
    return bytes(out)


class L4:
    """One NET/ROM transport frame LinBPQ sent us."""

    def __init__(self, p):
        self.org, self.dst = dec_call(p[0:7]), dec_call(p[7:14])
        self.hdr, self.data = p[15:20], p[20:]
        self.op = self.hdr[4]
        self.tx, self.rx = self.hdr[2], self.hdr[3]

    @property
    def kind(self):
        return self.op & 15

    def __str__(self):
        name = {1: "CONN REQ", 2: "CONN ACK", 3: "DISC REQ", 4: "DISC ACK", 5: "INFO",
                6: "INFO ACK"}.get(self.kind, str(self.kind))
        s = f"NET/ROM {self.org}>{self.dst} {name} tx{self.tx} rx{self.rx}"
        if self.kind == INFO:
            s += f" {len(self.data)} bytes" + (" (more follows)" if self.op & MORE else "")
        return s


class Far:
    """The far node: LinBPQ's KISS TNC, and its L2 and NET/ROM peer.

    It acks every I frame at L2 at once (L2 is not under test), and
    sends L4 frames only when the scenario asks.
    """

    def __init__(self, log):
        self.log = log
        self.srv = socket.socket()
        self.srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.srv.bind(("127.0.0.1", 0))
        self.srv.listen(1)
        self.port = self.srv.getsockname()[1]
        self.s = None
        self.vs = self.vr = 0
        self.l4 = []
        self.lock = threading.Lock()
        self.up = threading.Event()
        self.their = b""      # LinBPQ's circuit index and id
        self.rx = 0           # next L4 sequence number we expect from LinBPQ
        self.tx = 0           # next L4 sequence number we send

    def accept(self, timeout):
        self.srv.settimeout(timeout)
        self.s, _ = self.srv.accept()
        threading.Thread(target=self._reader, daemon=True).start()

    def _send(self, body):
        self.s.sendall(kiss(body))

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
                    if len(buf) > 15 and buf[0] == 0:
                        self._frame(bytes(buf[1:]))
                    buf = bytearray()
                elif b == FESC:
                    esc = True
                else:
                    if esc:
                        b = {TFEND: FEND, TFESC: FESC}.get(b, b)
                        esc = False
                    buf.append(b)

    def _frame(self, body):
        if dec_call(body[0:7]) != ME:
            return
        ctl = body[14]
        cmd = bool(body[6] & 0x80)
        with self.lock:
            if ctl & 1 == 0:
                ns, pf = (ctl >> 1) & 7, ctl & PF
                if ns == self.vr:
                    self.vr = (self.vr + 1) & 7
                    if body[15] == 0xCF:
                        f = L4(body[16:])
                        self.log(f"RX  {f}")
                        self.l4.append(f)
                self._send(frame((self.vr << 5) | (PF if pf else 0) | RR, cmd=False))
            elif ctl & 3 == 1 and cmd and ctl & PF:
                self._send(frame((self.vr << 5) | PF | RR, cmd=False))
            elif ctl & ~PF & 0xFF == UA:
                self.up.set()

    def send_ui_nodes(self):
        self._send(ax_call("NODES", bit7=True) + ax_call(ME, last=True)
                   + bytes([UI, 0xCF, 0xFF]) + b"TST   ")

    def send_sabm(self):
        self._send(frame(SABM | PF))

    def send_l4(self, l4, note):
        self.log(f"TX  {note}")
        l3 = nr_call(ME) + nr_call(NODE) + bytes([7])
        with self.lock:
            self._send(frame((self.vr << 5) | (self.vs << 1), l3 + l4, pid=0xCF))
            self.vs = (self.vs + 1) & 7

    def info(self, data):
        self.send_l4(self.their + bytes([self.tx, self.rx, INFO]) + data,
                     f"INFO tx{self.tx} rx{self.rx} {data!r}")
        self.tx = (self.tx + 1) & 0xFF

    def info_ack(self, rx, nak=False):
        self.send_l4(self.their + bytes([0, rx, INFO_ACK | (NAK if nak else 0)]),
                     f"INFO ACK rx{rx}" + (" NAK" if nak else ""))

    def wait(self, pred, timeout):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            with self.lock:
                for x in self.l4:
                    if pred(x):
                        self.l4.remove(x)
                        return x
            time.sleep(0.05)
        return None

    def wait_info(self, n, timeout):
        got, end = [], time.monotonic() + timeout
        while len(got) < n and time.monotonic() < end:
            x = self.wait(lambda f: f.kind == INFO, 0.5)
            if x:
                got.append(x)
        return got

    def close(self):
        for s in (self.s, self.srv):
            try:
                if s:
                    s.close()
            except OSError:
                pass


class Agw:
    """A minimal AGW application client."""

    def __init__(self, port):
        self.s = socket.create_connection(("127.0.0.1", port), timeout=10)
        self.s.settimeout(None)
        self.frames = []
        self.lock = threading.Lock()
        threading.Thread(target=self._reader, daemon=True).start()

    def send(self, kind, frm="", to="", data=b"", port=0, pid=0):
        h = struct.pack("<B3xcxBx10s10sI4x", port, kind.encode(), pid, frm.encode(), to.encode(), len(data))
        self.s.sendall(h + data)

    def _reader(self):
        buf = b""
        while True:
            try:
                d = self.s.recv(4096)
            except OSError:
                return
            if not d:
                return
            buf += d
            while len(buf) >= 36:
                n = struct.unpack("<I", buf[28:32])[0]
                if len(buf) < 36 + n:
                    break
                h, data, buf = buf[:36], buf[36:36 + n], buf[36 + n:]
                with self.lock:
                    self.frames.append((chr(h[4]), h[0], h[8:18].split(b"\0")[0].decode(),
                                        h[18:28].split(b"\0")[0].decode(), data))

    def wait(self, kind, timeout):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            with self.lock:
                for f in self.frames:
                    if f[0] == kind:
                        self.frames.remove(f)
                        return f
            time.sleep(0.05)
        return None

    def close(self):
        try:
            self.s.close()
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


def _open_and_write(far, agw, r):
    """Bring up L2 and an L4 circuit to the app; the app writes PAYLOAD.

    Returns the INFO frames LinBPQ sent for it (two, if all is well).
    """
    agw.send("X", frm=APP)
    if not agw.wait("X", 5):
        raise RuntimeError(f"AGW register of {APP} not answered")
    r.log(f"AGW application registered {APP}")

    far.send_ui_nodes()           # so LinBPQ has a route back to N0TST
    time.sleep(1)
    far.send_sabm()
    if not far.up.wait(5):
        raise RuntimeError("no UA to SABM")
    r.log("L2 link up")
    time.sleep(1)

    # CONN REQ: our circuit index 1, id 1, window 4, user N0USR at N0TST
    far.send_l4(bytes([1, 1, 0, 0, CONN_REQ, 4]) + nr_call("N0USR") + nr_call(ME), "CONN REQ")
    ack = far.wait(lambda f: f.kind == CONN_ACK, 10)
    if ack is None:
        raise RuntimeError("no CONN ACK")
    far.their = bytes(ack.hdr[2:4])

    far.info(b"TESTAPP\r")        # the application command: the circuit goes to the app
    conn = agw.wait("C", 15)
    if conn is None:
        raise RuntimeError("the application never got the connect")
    r.log(f"AGW app: connected from {conn[2]}")

    time.sleep(3)                 # take and ack whatever LinBPQ has sent so far
    with far.lock:
        seen = [f for f in far.l4 if f.kind == INFO]
        far.l4.clear()
    far.rx = (max((f.tx for f in seen), default=-1) + 1) & 0xFF
    far.info_ack(far.rx)
    time.sleep(1)

    r.log(f"--- the app writes {len(PAYLOAD)} bytes in one AGW frame")
    agw.send("D", frm=APP, to=conn[2], data=PAYLOAD, port=conn[1], pid=0xF0)
    first = far.wait_info(2, 5)
    if len(first) != 2:
        raise RuntimeError(f"expected two INFO frames for the write, got {len(first)}")
    if b"".join(f.data for f in first) != PAYLOAD:
        raise RuntimeError("the first send does not carry the app's write")
    return first


def _compare(r, sent, resent):
    for s, x in zip(sent, resent):
        if x.data == s.data and (x.op & MORE) == (s.op & MORE):
            continue
        lost = len(s.data) - len(x.data)
        if lost > 0 and s.data.startswith(x.data):
            at = PAYLOAD.find(s.data)
            r.fail(f"resent tx{x.tx} is {lost} bytes short: {len(x.data)} bytes, sent as "
                   f"{len(s.data)}; bytes {at + len(x.data)}..{at + len(s.data) - 1} "
                   f"of the app's write are gone")
        else:
            r.fail(f"resent tx{x.tx} differs from the frame sent ({len(x.data)} bytes, op "
                   f"{x.op:#04x}; sent {len(s.data)} bytes, op {s.op:#04x})")


def scenario_timer(far, agw, r):
    first = _open_and_write(far, agw, r)
    r.log("--- no L4 ack; wait for LinBPQ's L4 timer (L4TIMEOUT=10) to resend")
    again = far.wait_info(2, 30)
    if len(again) != 2:
        r.fail(f"expected both INFO frames again, got {len(again)}")
        return
    _compare(r, first, again)


def scenario_nak(far, agw, r):
    first = _open_and_write(far, agw, r)
    r.log("--- NAK the first frame (ask for it again, ack nothing)")
    far.info_ack(first[0].tx, nak=True)
    again = far.wait_info(1, 5)   # well inside the 10 s L4 timer
    if len(again) != 1:
        r.fail("no resend after the NAK")
        return
    _compare(r, first[:1], again)


SCENARIOS = {"timer": scenario_timer, "nak": scenario_nak}
DEFAULT = ["timer", "nak"]


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def run_scenario(name, linbpq, work_dir=None):
    """Start a fresh LinBPQ, play one scenario against it, return a Result."""
    r = Result(name)
    work = Path(work_dir or tempfile.mkdtemp(prefix=f"l4repro-{name}-"))
    work.mkdir(parents=True, exist_ok=True)
    (work / "logs").mkdir(exist_ok=True)
    far = Far(r.log)
    agw_port = _free_port()
    (work / "bpq32.cfg").write_text(CONFIG.format(kiss_port=far.port, agw_port=agw_port))
    out = open(work / "linbpq.out", "wb")
    exe = os.path.abspath(linbpq if os.sep in linbpq else shutil.which(linbpq) or linbpq)
    proc = subprocess.Popen([exe], cwd=work, stdout=out,
                            stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
    agw = None
    try:
        far.accept(30)
        r.log(f"LinBPQ connected to our KISS port {far.port}")
        time.sleep(1)
        agw = Agw(agw_port)
        SCENARIOS[name](far, agw, r)
    except Exception as e:  # setup trouble, not the fault under test
        r.fail(f"scenario could not run: {e!r}; see {work}")
    finally:
        if agw:
            agw.close()
        far.close()
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
