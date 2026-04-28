# Getting started

A walk from a clean Linux box to a node serving a telnet session,
fact-checked against the LinBPQ source.

LinBPQ runs on Linux (Raspberry Pi, x86, generic ARM), macOS, and
the BSDs.  This page focuses on Linux — the build is the same shape
on Mac (`make -f makefile_mac`) and the runtime is identical.

!!! note "Upstream and source"
    Re-presentation of John Wiseman's
    [LinBPQ Installation page][upstream] and
    [BPQ32 Documents index][bpq32docs].  Build steps cross-checked
    against `makefile`; command-line flags against `LinBPQ.c`.

[upstream]: https://www.cantab.net/users/john.wiseman/Documents/InstallingLINBPQ.html
[bpq32docs]: https://www.cantab.net/users/john.wiseman/Documents/BPQ32%20Documents.htm

## Build dependencies

Debian / Ubuntu / Raspberry Pi OS:

```bash
sudo apt install build-essential libpaho-mqtt-dev libjansson-dev \
  libminiupnpc-dev libconfig-dev libpcap-dev zlib1g-dev
```

The build links against `paho-mqtt`, `jansson`, `miniupnpc`,
`libconfig`, `libpcap`, `zlib`, and `pthread` — see the `LIBS=`
line in `makefile`.

To build without I²C support (older Pi boards or non-Pi hardware
without `/dev/i2c-*`):

```bash
make noi2c
```

To build without MQTT:

```bash
make EXTRA_CFLAGS=-DNOMQTT
```

(NetBSD and FreeBSD builds enable `-DNOMQTT` automatically.)

## Build

From a checkout of this repo:

```bash
make
```

Produces `./linbpq` plus a stack of intermediate `.o` files.  On
macOS use `make -f makefile_mac`; FreeBSD / NetBSD are detected
automatically by `uname -s`.

## Optional capabilities

If you want LinBPQ to bind privileged TCP/UDP ports below 1024
(e.g. telnet on TCP/23) or use the BPQEther driver, grant the
binary the necessary capabilities once:

```bash
sudo apt install libcap2-bin
sudo setcap "CAP_NET_ADMIN=ep CAP_NET_RAW=ep CAP_NET_BIND_SERVICE=ep" linbpq
```

For ports above 1023 — the configuration this guide uses — neither
capabilities nor `root` are required.  Avoid running as root.

## Web-management assets

The web-admin pages live in `HTML/` next to the binary:

```bash
mkdir -p HTML
# populate from the repo, or fetch upstream's HTMLPages.zip
```

Without these files the daemon still runs, but `http://host:HTTPPORT/`
will 404.

## Minimum viable cfg

Put this in `bpq32.cfg` next to the binary:

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

Replace `N0CALL` with your callsign, set a Maidenhead `LOCATOR`
if you have one (or `NONE`), and pick TCP/HTTP ports that are
free on your box.

The `USER=` line declares a single login `test` / `test` with
sysop rights.  Use a real password before exposing the node to a
network.

## First boot

```bash
./linbpq
```

You should see:

```
G8BPQ AX25 Packet Switch System Version 6.0.25.23 February 2026
Copyright © 2001-2026 John Wiseman G8BPQ
Current Directory is /…/linbpq
…
Initialising Port 01     Telnet Server
```

Then a telnet client to `localhost:8010` lands on the node prompt:

```bash
telnet localhost 8010
```

```
user: test
password: test
Welcome test to N0CALL Telnet Server
GB7XXX:N0CALL-1} Connected to N0CALL TEST
```

`BYE` (or `B`) to disconnect.

## Optional command-line flags

`linbpq -h` prints:

```
-l path or --logdir path          Path for log files
-c path or --configdir path       Path to Config file bpq32.cfg
-d path or --datadir path         Path to Data Files
-v                                Show version and exit
```

Useful for separating runtime data from a read-only install
directory, or for running multiple instances side by side.

Positional arguments after the flags select extra subsystems:

| Argument | Effect |
|----------|--------|
| `mail` | Start the BPQMail BBS alongside the node (`linmail.cfg`) |
| `chat` | Start the chat server alongside the node (`chatconfig.cfg`) |
| `daemon` | Detach from the controlling terminal |
| `logdir=path` | Same as `-l path` (legacy form, supported for compat) |

`bpq32.cfg` keywords `LINMAIL` and `LINCHAT` are equivalent to
the `mail` / `chat` positional arguments; pick whichever style
suits your launcher.

## Stopping the node

`Ctrl+C` from the console, or `SIGTERM` / `SIGINT` when running
detached:

```bash
pkill -INT linbpq
```

Persistent state (NODES table, MH list, BBS message store, chat
rooms) is checkpointed periodically and reloaded on next boot.

## Run as a service

For a long-running node, drive it from systemd.  `/etc/systemd/system/linbpq.service`:

```ini
[Unit]
Description=LinBPQ packet node
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/linbpq
ExecStart=/home/pi/linbpq/linbpq
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now linbpq
journalctl -u linbpq -f
```

Mirror the working directory (`/home/pi/linbpq`) on whatever
account you give the service.  The node writes its persistent
state into the same directory it was launched from unless `-d`
points elsewhere.

## What to do next

- [Configuration reference][config-ref] — every supported cfg
  keyword
- [Node prompt commands][node-commands] — what to type once
  you're on the prompt
- [Subsystems][subsystems] — when you're ready to enable BBS,
  Chat, APRS

[config-ref]: ../configuration/reference.md
[node-commands]: ../node-commands.md
[subsystems]: ../subsystems/index.md
