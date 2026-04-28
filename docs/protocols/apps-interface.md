# Applications Interface

LinBPQ exposes a TCP-based Applications Interface that lets an
external program show up at the node prompt as a registered
application — users type the application's command word (or
connect to the application's callsign), BPQ dials out to the
external program, and a bidirectional byte stream is glued
together between the user's session and the application's
TCP socket.

This page covers two related but distinct things, both from
an application-implementor's perspective:

1. **The Apps Interface (inbound)** — your application is a
   destination users connect *to*.  BPQ dials your TCP listener
   when a user invokes the application.
2. **Originating a binary-transparent connection (outbound)** —
   your application is a *source* that wants BPQ to dial a
   remote callsign and hand back a clean byte pipe.  Not part
   of the Apps Interface proper, but a common follow-up
   question.

!!! note "Upstream and source"
    Re-presentation of John Wiseman's
    [LinBPQ Applications Interface][upstream] page,
    cross-checked against the LinBPQ source.

[upstream]: https://www.cantab.net/users/john.wiseman/Documents/LinBPQ%20Applications%20Interface.html

## Apps Interface (inbound)

The Apps Interface gives you a single TCP socket (per
application) on which BPQ delivers user sessions, one connection
at a time.  BPQ dials *out* to your listener — your app is a TCP
*server* on `127.0.0.1`, BPQ is the client.

### Wiring up an application

Two pieces of `bpq32.cfg` are needed.

**1.  Inside the Telnet driver's `CONFIG ... ENDPORT` block,
declare the slot array:**

```ini
PORT
 ID=Telnet
 DRIVER=Telnet
 CONFIG
 TCPPORT=8010
 HTTPPORT=8080
 MAXSESSIONS=10
 USER=test,test,N0CALL,,SYSOP
 CMDPORT 23 63000 63001
ENDPORT
```

`CMDPORT` takes a list of TCP ports.  Each whitespace- or
comma-separated entry occupies a slot, indexed from 0:

| Slot | TCP port |
|---|---|
| 0 | 23 |
| 1 | 63000 |
| 2 | 63001 |

Up to 33 slots (0–32) are accepted.  An entry of `0` is a
sentinel — that slot is unconfigured and connects to it will
be rejected.

`LINUXPORT` is an accepted alias for `CMDPORT` if you prefer
the historical name.

**2.  At top level, declare each application that maps to a
slot:**

```ini
APPLICATION 1,LINUX,C 2 HOST 0 S
APPLICATION 2,DEMO,C 2 HOST 1 S
```

The third field is the *node-command line* run when the user
types the application word.  `C 2 HOST <slot>` is what wires
the user's session to the slot's TCP listener — the `2` is
the BPQ port that hosts the Telnet driver (the same port the
user is currently on); the `<slot>` is the index into `CMDPORT`.

Optional flags follow `C <port> HOST <slot>`:

| Flag | Effect |
|---|---|
| `S` | When the application drops, return the user to the node prompt rather than disconnecting the whole session. |
| `NOCALL` | Suppress the auto-sent callsign line (see below). |
| `K` | Send periodic keepalive lines so a long-idle app doesn't get reaped by the L4 idle timer. |
| `TRANS` | Put the socket in **binary-transparent mode** — no line discipline, raw bytes both directions. |

Flags can appear in any order after the `<slot>`.

### What your application sees on the socket

When a user invokes the application (or another node connects
to its callsign) BPQ opens a TCP connection to
`127.0.0.1:<your port>` and immediately delivers:

```
<USERCALL>\r\n
```

…unless `NOCALL` is set, in which case nothing is sent up
front.  The user is shown `*** Connected to <APPL>\r` on
their side at the same moment.

After the callsign line, both sides exchange application bytes.

#### Default vs `TRANS` mode

The default isn't a clean byte pipe — BPQ applies a textual
line discipline in *both* directions and interprets a few
control sequences:

| | Default (no `TRANS`) | `TRANS` |
|---|---|---|
| **App → user** (BPQ reads your socket) | Bytes are *buffered* until a CR (`\r`) or LF (`\n`) arrives, then forwarded to the user.  A CR-NUL pair is rewritten to CR-LF (and the inserted LF is echoed back to your socket).  Lines longer than 255 bytes are split at 255-byte boundaries before being handed to the node. | Raw passthrough — bytes are forwarded in `recv()`-sized chunks the moment they arrive, no scanning, no buffering, no rewriting. |
| **User → app** (BPQ writes your socket) | Every CR (`\r`) in the outbound stream is *expanded* to CR-LF (`\r\n`).  Optional codepage → UTF-8 conversion can happen here too (controlled by the per-session UTF8 flag from BPQTerm-style clients). | Raw passthrough — bytes go out in the same order and quantity BPQ received them from the node side. |
| **Telnet IAC** (`0xFF`) | Interpreted as a telnet command byte and swallowed if it forms a valid IAC sequence. | Passed through verbatim. |

In short: **default mode is line-oriented text, biased toward
human terminals**.  It's fine for any protocol whose unit of
work is a CR-terminated line of 7-bit text.  It's *not* fine
for binary transfers, length-framed protocols, anything that
relies on an unmodified `0xFF` byte (FBB B2 attachments,
arbitrary file content), or anything where you want zero
bytes between an app `write()` and the user receiving them.

When the user disconnects (or your app closes the socket) BPQ
either:

- Returns them to the node prompt (with the `S` flag), or
- Drops the whole session (without `S`).

#### Control text BPQ injects on the user's session

| User sees | When |
|---|---|
| `*** Connected to <APPL>` | Your TCP listener accepted (text-mode only). |
| `*** Disconnected from Stream <n>` | Either side closed the socket (text-mode only — `TRANS` mode just closes). |
| `Error - Invalid HOST Port` | Slot index out of range, or that slot is `0` in the `CMDPORT` array. |
| `Keepalive\r` | If the `K` flag is set and the session has been idle long enough that the L4 idle timer would otherwise reap it. |

### Listener — `inetd`, `systemd`, or your own daemon

Your application has to be listening on `127.0.0.1:<port>`
when BPQ dials.  Three common ways to arrange that, easiest
first.

#### Option A — let `inetd` run your program

`inetd` is the original Unix "Internet superserver".  It's a
long-running daemon that holds open every TCP/UDP port listed
in its config; when a connection arrives it accepts the socket,
forks, and execs the program you've nominated for that port —
with stdin / stdout / stderr already wired to the socket.  Your
program just reads stdin and writes stdout, exits when it's
done, and `inetd` is ready for the next connection.

For a BPQ app this is ideal: every user gets their own fresh
process, you don't have to write any networking code, and
crashes in one session can't leak state into the next.

Install on Debian / Ubuntu (Hibbian package included):

```bash
sudo apt install openbsd-inetd
```

Then two small config changes.

`/etc/services` is a system-wide name → port-number table.
Pick any unused port above 1024 — say 63000 — and give it a
name:

```
bpqdemo        63000/tcp   # BPQ Demo App
```

`/etc/inetd.conf` tells `inetd` which program to run for that
service:

```
bpqdemo    stream    tcp    nowait    linbpq    /usr/local/bin/bpqdemo
```

Field by field:

| Field | Value | Meaning |
|---|---|---|
| Service | `bpqdemo` | Looked up in `/etc/services` to get the port number. |
| Socket type | `stream` | TCP. |
| Protocol | `tcp` | TCP. |
| Wait | `nowait` | Fork a new process per connection rather than serializing. |
| User | `linbpq` | Run the program as this user (the same user `linbpq` itself runs as is fine). |
| Program | `/usr/local/bin/bpqdemo` | Absolute path to the binary. |

(There are usually a couple more fields after the program path
for arguments — `man 5 inetd.conf` if you need them.)

Reload `inetd` to pick up the change:

```bash
sudo systemctl reload inetd
# or, on older systems:
sudo killall -HUP inetd
```

Now drop your `bpq32.cfg` `CMDPORT 63000` (or wherever 63000
is in your slot list) and an `APPLICATION` line, and the next
connect will fire your program.

The standard variant `xinetd` does the same thing with a
per-service config file in `/etc/xinetd.d/bpqdemo` instead of a
shared `inetd.conf` line — the `inetd.conf` fields above all
have direct equivalents (see `man 5 xinetd.conf`).

#### Option B — let `systemd` do it

systemd has its own equivalent of `inetd` built in.  Two unit
files do the work: a `.socket` unit holds the listening port,
and a templated `.service` unit runs an instance per connection.

`/etc/systemd/system/bpqdemo.socket`:

```ini
[Socket]
ListenStream=127.0.0.1:63000
Accept=yes

[Install]
WantedBy=sockets.target
```

`/etc/systemd/system/bpqdemo@.service`:

```ini
[Unit]
Description=BPQ demo app, per-connection instance

[Service]
ExecStart=/usr/local/bin/bpqdemo
StandardInput=socket
StandardOutput=socket
User=linbpq
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now bpqdemo.socket
```

Now every accepted connection starts a fresh `bpqdemo@.service`
instance with stdin/stdout already plugged into the socket —
same model as `inetd`, but managed by systemd so logs land in
`journalctl -u bpqdemo@*` and lifecycle is visible to
`systemctl status`.

#### Option C — your own daemon

Nothing stops you from writing a long-running listener
yourself: open a socket, `bind()`, `listen()`, `accept()` in a
loop, fork or thread per accepted connection.  This is more
work than the above but lets you carry shared state across
sessions (a connected-user table, a database handle, etc.).

BPQ doesn't care which option you choose — it just connects to
`127.0.0.1:<port>` and starts moving bytes.

### A minimal echo app

```python
#!/usr/bin/env python3
import sys, signal, time

# Read the callsign BPQ sends on connect (one line).
caller = sys.stdin.readline().strip()
print(f"Hello {caller}, welcome to the demo app.  Type 'exit' to leave.", flush=True)

for line in sys.stdin:
    line = line.rstrip("\r\n")
    if line.lower() == "exit":
        print("bye", flush=True)
        break
    print(f"  echo: {line}", flush=True)
```

Wire it through `inetd` or systemd as above and connect from
the node prompt:

```
LINUX
```

(or `C N0CALL-9` if you've given the application a callsign on
the `APPLICATION` line — see the
[Configuration reference][cfg]).

[cfg]: ../configuration/reference.md

### Binary-transparent application sockets

Add `TRANS` to the `APPLICATION` line and the socket carries
raw bytes both ways — no `\r\n` translation, no FLMSG frame
sniffing, no internal line buffering.  Useful for binary
protocols (file transfer, image push, custom framings) and for
applications that want to handle their own line discipline.

```ini
APPLICATION 3,BINARY,C 2 HOST 2 TRANS S
```

Caveats:

- The auto-sent `<USERCALL>\r\n` still appears unless you also
  add `NOCALL` — strip or skip it on the app side, or pair
  `TRANS` with `NOCALL`.
- Streams are still bidirectional TCP — there's no record
  framing.  If your binary protocol needs message boundaries,
  put them in the protocol.

### Authentication

There isn't any.  Anybody who reaches the application's
listener bypass the BPQ user check entirely.  Two consequences:

- **Bind to `127.0.0.1` only.**  BPQ always connects to
  loopback; binding to `0.0.0.0` exposes your app to the open
  network with no auth.
- **Trust the callsign string for identification, not for
  authorisation.**  BPQ sends what the connecting user
  authenticated as, but the application has no way to verify
  the chain of trust independently.  If you need authorisation
  (sysop-only commands, per-user state) maintain your own user
  table keyed on callsign.

### Other application registration paths

The `APPLICATION` line's third field can be any node command,
not just `C <port> HOST <slot>`:

```ini
APPLICATION 4,DX,C 2 N0DXC          ; downlink connect
APPLICATION 5,DXSPIDER,C 2 HOST 3 S ; via apps interface
```

So a third-party DX cluster reachable as a callsign on AX.25
can be wired to a single command word too — the
implementation behind it is whatever the node command does.

## Originating a binary-transparent connection (outbound)

A different problem: your application has identified a remote
callsign it wants to connect to over AX.25 / NET/ROM, and
wants a clean byte pipe to it through BPQ.  Two practical
options.

### Option 1 — AGW protocol (recommended)

The AGW emulator is the cleanest path.  Enable it in
`bpq32.cfg`:

```ini
AGWPORT=8000
AGWSESSIONS=20
AGWMASK=1
```

Now any AGW-protocol client can connect to TCP/8000 and use
the standard SV2AGW frame format.  The protocol is
binary-record-framed: each message is a 36-byte header
followed by 0..N payload bytes.  Header layout:

| Offset | Size | Field | Meaning |
|---:|---:|---|---|
| 0 | 1 | Port | BPQ port number (0-indexed in AGW). |
| 1 | 3 | filler | Zero. |
| 4 | 1 | DataKind | ASCII kind byte (see below). |
| 5 | 1 | filler | Zero. |
| 6 | 1 | PID | AX.25 PID for I/UI frames (e.g. 0xF0 for text). |
| 7 | 1 | filler | Zero. |
| 8 | 10 | callfrom | Source callsign, NUL-padded. |
| 18 | 10 | callto | Destination callsign, NUL-padded. |
| 28 | 4 | DataLength | Payload length, little-endian. |
| 32 | 4 | reserved | Zero. |

The DataKind values you'll typically use:

| Kind | Direction | Meaning |
|---|---|---|
| `X` | client → BPQ | Register your callsign for incoming-connect routing. |
| `G` | client → BPQ | Ask for the port table; BPQ replies with `G`. |
| `C` | client → BPQ | Connect to `callto` from `callfrom` on `Port`. |
| `v` | client → BPQ | Same, but with via-digi list in payload. |
| `D` | both | Connected-mode data (in-band session bytes). |
| `M` | client → BPQ | Send a UI frame. |
| `K` | both | Raw KISS frame in/out. |
| `C` | BPQ → client | Connect-confirmation (mirrors the request). |
| `d` | BPQ → client | Remote disconnected. |
| `R` | BPQ → client | AGW software version. |
| `g` | BPQ → client | Single-port descriptor. |

Typical session shape, from the application's point of view:

```
client → BPQ : 'X'  callfrom=N0CALL-1                  (register)
client → BPQ : 'G'                                     (port query)
BPQ    → client : 'G' payload="2;Port1 desc;Port2 desc;"
client → BPQ : 'C' Port=2 callfrom=N0CALL-1 callto=N0DST   (connect)
BPQ    → client : 'C' Port=2 callfrom=N0CALL-1 callto=N0DST  (confirmed)
client → BPQ : 'D' ... payload bytes ...               (data out)
BPQ    → client : 'D' ... payload bytes ...            (data in)
...
BPQ    → client : 'd' ... (remote disconnect notification)
```

`D`-records are arbitrary binary bytes — the AX.25 link layer
delivers them in order, end-to-end through whatever
combination of L2 hops, NET/ROM, AX/IP-UDP and digipeating
gets the connection to its destination.  No line discipline is
applied; this is *the* binary-transparent path through BPQ.

There are mature AGW-protocol libraries available in most
languages (`agwpe-py` for Python, `agwpe.NET` for C#, embedded
in Direwolf companions for C, etc.) — using one of those is
much less work than rolling the framing yourself.

`AGWMASK` is a bitmask of `APPLICATION` slots an AGW client is
allowed to register against.  `AGWMASK=1` permits slot 1 only;
`AGWMASK=0xFF` permits the first eight; etc.  Without a
matching mask bit the AGW client can still send/receive but
won't appear as a registered destination for incoming
connects.

### Option 2 — FBB-mode telnet

If AGW isn't an option, a simpler-but-rougher path exists
through the Telnet driver in *FBB mode*.  In `bpq32.cfg`'s
Telnet `CONFIG ... ENDPORT` block, alongside `TCPPORT=`:

```
FBBPORT=8011
```

Connect to TCP/8011 instead of TCP/8010, and BPQ skips telnet
line discipline (no IAC negotiation, no `\r\n` rewriting).  You
still have to log in — send `<user>\r<password>\r` — then issue
node commands.  `C <port> <call>` opens a connection; after
`*** Connected to <call>\r` you can exchange bytes more or
less binary-transparently with the remote, but BPQ will still
inject control lines (e.g. `*** Disconnected\r`) at session
boundaries and may interleave node-prompt status with your
data if the user-side session goes interactive.

This is the path used by the FBB inter-BBS forwarding
protocol — it works, and it's simple, but it wasn't designed
for arbitrary binary apps and has subtle textual seams at
session edges.  Prefer AGW unless you're explicitly targeting
the FBB protocol or a tooling stack that already speaks
FBB-mode telnet.

### Comparison at a glance

| | AGW | FBB-mode telnet | Apps Interface (CMDPORT) |
|---|---|---|---|
| Direction | originate from app, also accept inbound | originate from app | inbound only — BPQ dials your app |
| Framing | record-based (36-byte header + payload) | byte stream | byte stream |
| Line discipline | n/a — records are binary | none in FBB mode | text by default; `TRANS` for raw |
| Authentication | none (loopback-bind) | telnet `USER=` line | none (loopback-bind) |
| Multiple sessions per connection | yes (multiplexed by `callfrom`/`callto`) | one per TCP connection | one per TCP connection |
| Best for | new apps doing originate + accept | quick scripts / FBB protocol | inbound-only apps glued to a node command |
