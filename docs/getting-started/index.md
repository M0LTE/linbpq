# Getting started

!!! warning "Stub page"
    Pending rewrite from upstream
    [BPQ32 Documents.htm][bpq32-docs] +
    [LinBPQ install / build notes][bpq-installguide]
    plus the build steps the integration suite uses.  Tracking
    in [docs/plan.md](../plan.md).

A self-contained walk from a clean Linux box to a node serving
a telnet session and a working BBS — fact-checked against the
integration suite that ships alongside this repo.

## What to build

Linbpq builds from C source in this repo into a single
binary (`linbpq`).  The build dependencies on Debian/Ubuntu:

```bash
sudo apt install build-essential libpaho-mqtt-dev libjansson-dev \
  libminiupnpc-dev libconfig-dev libpcap-dev zlib1g-dev
```

Then:

```bash
make
```

produces `./linbpq` plus a stack of intermediate `.o` files.

(Mac is `make -f makefile_mac`; FreeBSD / NetBSD detected
automatically by `uname -s`.)

## Minimum viable cfg

```ini
SIMPLE=1
NODECALL=N0CALL
NODEALIAS=TEST
LOCATOR=NONE

PORT
 ID=Telnet
 DRIVER=Telnet
 CONFIG
 TCPPORT=8010
 HTTPPORT=8080
 MAXSESSIONS=10
 USER=test,test,N0CALL,,SYSOP
ENDPORT
```

Replace `N0CALL` with your callsign, `IO91WJ`-style locator if
you have one (or `NONE`), and pick TCP/HTTP ports that are free.

## First boot

```bash
./linbpq
```

You should see something like:

```
G8BPQ AX25 Packet Switch System Version 6.0.25.23 February 2026
...
Initialising Port 01     Telnet Server
MQTT Enabled 0
```

…then a telnet client to localhost:8010 lands on the node prompt.

## Next steps

- [Configuration reference][config-ref] — every supported cfg
  keyword
- [Node prompt commands][node-commands] — what to type once
  you're on the prompt
- [Subsystems][subsystems] — when you're ready to enable BBS,
  Chat, APRS

[bpq32-docs]: https://www.cantab.net/users/john.wiseman/Documents/BPQ32%20Documents.htm
[bpq-installguide]: https://www.cantab.net/users/john.wiseman/Documents/LinBPQ.htm
[config-ref]: ../configuration/reference.md
[node-commands]: ../node-commands.md
[subsystems]: ../subsystems/index.md
