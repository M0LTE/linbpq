# LinBPQ documentation

!!! warning "Unofficial fork, AI-generated, in progress"
    [`M0LTE/linbpq`][thisrepo] — both the software in this repo
    and these docs — is a personal fork of [`g8bpq/linbpq`][upstreamrepo]
    used for patching, experimenting, and documenting.  John
    Wiseman G8BPQ is the author and authority for both the
    software and its official documentation; he distributes
    source through his GitHub repo and develops largely outside
    it.  Code in this fork may carry local patches, experiments
    or instrumentation that aren't in John's upstream.  Both
    streams sit downstream of John, made possible by the
    project's GPL — neither is authoritative.

    For canonical builds, get them from John.  For canonical
    documentation, see his [upstream HTML docs][bpqdocs].
    When this site or the binary built from this fork disagrees
    with John's upstream, treat John as right.

[thisrepo]: https://github.com/M0LTE/linbpq
[upstreamrepo]: https://github.com/g8bpq/linbpq

## LinBPQ vs BPQ32 — same software, different OS

John Wiseman G8BPQ's amateur-radio packet switch is a single
codebase (~150 C files) that builds on multiple operating
systems.  The names are historical:

| Name | Where it runs | What you get |
|---|---|---|
| **BPQ32** | Windows | `BPQ32.exe` plus `BPQ32.dll`, installed via an NSIS package; companion programs (BPQTerminal, BPQAPRS desktop, VCOMConfig) ship alongside |
| **LinBPQ** | Linux, macOS, FreeBSD, NetBSD | A single `linbpq` binary built with `make` |

Both are built from the same C sources, maintained by John and
distributed through [`g8bpq/linbpq`][upstreamrepo] on GitHub.
They share the same `bpq32.cfg` format, the same on-air wire
protocols, the same node-prompt commands, the same subsystems
(BBS, chat, APRS gateway, IP gateway), and the same web admin
UI.  Day-to-day operation is identical across platforms.

Where the two diverge:

- **Build / install shape**: NSIS installer on Windows; `make`
  + optional `setcap` on Linux.
- **Companion programs**: BPQTerminal, BPQAPRS, VCOMConfig and
  the BPQ Virtual Serial Port Driver are Windows-only desktop
  apps.  Linux equivalents are listed where appropriate (e.g.
  [QtBPQAPRS][qtbpqaprs] for the APRS map client).
- **A few drivers**: BPQ Ethernet uses raw sockets on Linux and
  WinPcap on Windows but speaks the same wire format; BPQ Virtual
  COM Ports are a Windows-only kernel-mode feature.

Everything in this site applies to both unless a page calls out
otherwise.  The [Getting started][getting-started] section has a
Linux page and a Windows page; the rest of the site is OS-agnostic.

[qtbpqaprs]: https://github.com/G8BPQ/QtBPQAPRS

## What it does

In one process the software provides:

- An AX.25 / NET/ROM packet switch
- A BBS (BPQMail) with FBB inter-BBS forwarding
- A real-time chat node
- An APRS gateway with iGate uplink
- An optional IP gateway for IP-over-AX.25 / AMPRNet

It speaks to radios over a long list of modems (KISS, Pactor
families, ARDOP, VARA, FLDigi, MULTIPSK, WinRPR, HSMODEM) and to
clients over Telnet, AGW, KISS-over-TCP, AX.25-over-UDP, NET/ROM-
over-TCP, MQTT, and a JSON / SNMP / Winlink CMS family.

## Where to start

<div class="grid cards" markdown>

- :material-rocket-launch: __[Getting started][getting-started]__

    Stand a node up from scratch — [Linux][gs-linux] (build, setcap,
    first boot) or [Windows][gs-windows] (NSIS installer, companion
    programs).  Same minimal `bpq32.cfg` either way.

- :material-cog: __[Configuration reference][config-ref]__

    Every cfg keyword the parser accepts, what subsystem owns it,
    cross-referenced to the source line that consumes it.

- :material-application-cog: __[Subsystems][subsystems]__

    BBS / mail, chat, APRS — what each does, how to enable it,
    the relationship between cfg keywords and runtime commands.

- :material-network: __[Protocols and interfaces][protocols]__

    AX.25, NET/ROM, AX/IP-over-UDP, KISS, FBB forwarding,
    Winlink CMS — the wire formats LinBPQ implements.

- :material-console: __[Node prompt commands][node-commands]__

    Reference for every command on the telnet node prompt.
    Generated from `Cmd.c::COMMANDS[]`.

</div>

## Why a re-presentation

[John Wiseman's docs][bpqdocs] are the authoritative source on
LinBPQ's behaviour and have been kept up to date for two
decades.  What this site adds is *organisation by audience and
task*: the upstream docs are arranged loosely as files-as-found,
while this site groups material by what someone actually wants
to do, with deep links into the source.

This site is a downstream re-presentation of John's docs, hosted
in a fork of his repo.  The technical content is meant to be
faithful to upstream and we cite John's pages prominently.
Where this site disagrees with John, treat John as right and
[file a GitHub issue][issues] against this fork so we can fix
the doc here.

[bpqdocs]: https://www.cantab.net/users/john.wiseman/Documents/
[getting-started]: getting-started/index.md
[gs-linux]: getting-started/index.md
[gs-windows]: getting-started/windows.md
[config-ref]: configuration/reference.md
[subsystems]: subsystems/index.md
[protocols]: protocols/index.md
[node-commands]: node-commands.md
[issues]: https://github.com/M0LTE/linbpq/issues
