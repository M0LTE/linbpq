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

## Two ways to install

Pick whichever fits your situation.  Both end up running the
same binary; the difference is who owns the install lifecycle.

| Path | Best for | Notes |
|---|---|---|
| **Hibbian apt repo** *(recommended)* | Debian 11/12/13, Ubuntu derivatives, Raspberry Pi OS | Maintained by a Debian packager.  Ships with a `systemd` unit, a service user, and standard FHS paths.  `apt upgrade` for updates. |
| **Build from source** | macOS, the BSDs, non-Debian Linux distros, or when you want to run a patched fork | What John publishes; what this repo's `make` produces.  You own start-up, paths and updates. |

Both produce a binary that reads `bpq32.cfg` and exposes the
same wire protocols.  Only the file layout and the start/stop
mechanics differ.

## Install via the Hibbian apt repo (recommended)

[Hibbian][hibbian] is a Debian package repository for amateur-
radio software, alongside packages for Direwolf, QtSoundModem,
QtTermTCP and similar.  Supported on Debian 11 (Bookworm),
12 (Bullseye), 13 (Trixie), and Ubuntu / Raspberry Pi OS
derivatives of those.

[hibbian]: https://guide.hibbian.org/

### Add the repo

The maintainer's [setup script][hibbian-setup] handles keyring
download and `sources.list` entry.  Or do it manually per the
[repo guide][hibbian-repo]:

```bash
# Fetch the keyring .deb that matches your distro release,
# then:
sudo apt install ./keyring-file.deb
sudo apt update
```

[hibbian-setup]: https://guide.hibbian.org/repo/
[hibbian-repo]: https://guide.hibbian.org/repo/

### Install LinBPQ

```bash
sudo apt install linbpq
```

The package installs:

- The `linbpq` binary.
- A `linbpq` system user the daemon runs as.
- A `systemd` unit at `/usr/lib/systemd/system/linbpq.service`.
- A skeleton config at `/etc/bpq32.cfg` — edit before first start.

### Edit the config

```bash
sudo "$EDITOR" /etc/bpq32.cfg
```

Set at minimum your callsign, alias, locator, sysop password,
and the Telnet port-block credentials.  See the
[Configuration reference][cfg] for the full keyword list.

Make the file readable by the service:

```bash
sudo chown :linbpq /etc/bpq32.cfg
sudo chmod 644 /etc/bpq32.cfg
```

### Start the service

```bash
sudo systemctl start linbpq
sudo systemctl enable linbpq        # start on boot
journalctl -u linbpq -f             # follow the log
```

The default Hibbian config exposes:

- HTTP web admin on `http://127.0.0.1:8008/`
- Telnet on `127.0.0.1:8010`
- FBB-mode (raw TCP for inter-BBS forwarding) on `127.0.0.1:8011`

You can change these in `/etc/bpq32.cfg`'s Telnet `PORT` block.

[cfg]: ../configuration/reference.md

### Updating

```bash
sudo apt update && sudo apt upgrade
sudo systemctl restart linbpq
```

### Quirks vs the build-from-source layout

- Config lives at `/etc/bpq32.cfg`, not next to the binary —
  match that when reading the rest of the docs.
- Persistent state and logs land under `/var/lib/linbpq/` and
  `/var/log/linbpq/` respectively (rather than the working
  directory model used by a hand-built install).  If you want to
  override paths, edit the systemd unit's `WorkingDirectory=`
  and `ExecStart=` line.
- The daemon runs as the `linbpq` user, not as `root` and not
  as the human operating the machine.  Files written by the
  daemon are owned by `linbpq:linbpq`; if you edit one by hand
  you may need to fix ownership before restart.

## Build from source

For macOS, the BSDs, non-Debian Linux distros, or to run a
patched fork (this repo, for example), build from source.
What follows is what `make` does in this checkout — same shape
as John's upstream build.

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

## Run as a service (source-build only)

The Hibbian package ships a systemd unit out of the box; this
section is for hand-built installs.  `/etc/systemd/system/linbpq.service`:

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
