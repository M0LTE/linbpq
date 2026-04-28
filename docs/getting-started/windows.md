# Getting started — Windows (BPQ32)

The BPQ32 Windows build and the Linux LinBPQ build are the *same
codebase* — `bpq32.dll` on Windows is built from the same C
sources as the `linbpq` binary on Linux.  Configuration, behaviour
and the wire side are identical; only the install shape and the
host-OS plumbing differ.

This page is the Windows companion to the Linux-focused
[Getting started][gs].  If you've already configured BPQ32 on one
side, the other will be familiar.

[gs]: index.md

!!! note "Upstream and source"
    Re-presentation of John Wiseman's
    [BPQ32 Installation][upstream-install] page and Ken KD6PGI's
    [BPQ Quickstart Guide][upstream-quick].

[upstream-install]: https://www.cantab.net/users/john.wiseman/Documents/BPQ32%20Installation.htm
[upstream-quick]: https://www.cantab.net/users/john.wiseman/Documents/Quickstart_Guide.html

## Install

The Windows installer is an [NSIS][nsis] package distributed
through John's site (and the `bpq32` groups.io group).  It
detects a running BPQ32 instance and refuses to upgrade until
the existing one is closed.

[nsis]: https://nsis.sourceforge.io/

Following Windows convention, the installer separates code from
data:

| Path | Contents |
|---|---|
| `C:\Program Files\BPQ32\` (32-bit Windows) | Binaries: `BPQ32.exe`, `BPQ32.dll`, support utilities. |
| `C:\Program Files (x86)\BPQ32\` (64-bit Windows) | Same — BPQ32 is a 32-bit build. |
| `%appdata%\BPQ32\` | `bpq32.cfg`, log files, persistent state. |

Open **Start Menu → BPQ32 → View Configuration Folder** to land in
`%appdata%\BPQ32\`.

Bundled example configs (Minimal / APRS / Small / Large) sit in
the program directory — copy one to `%appdata%\BPQ32\bpq32.cfg`
and edit.

## Companion programs in the installer

| Program | Purpose |
|---|---|
| `BPQ32.exe` | The node process itself.  Runs in a console window. |
| `BPQTerminal.exe` | Local terminal client; see [BPQTerminal][term]. |
| `VCOMConfig.exe` | Configure BPQ Virtual COM ports for serial-port-expecting client apps. |
| `BPQAPRS.exe` | APRS desktop map and messaging client; see [BPQAPRS map client][aprs-map]. |
| `BPQHostModes.exe` | TNC-host-mode emulator for legacy applications.  See [Host Mode Emulator][hostmode]. |
| `ClearRegistryPath` / `SetRegistryPath` | Manage BPQ's registry key (advanced). |
| `Uninstall.exe` | Removes binaries; preserves `%appdata%\BPQ32\`. |

[term]: ../clients/bpqterminal.md
[aprs-map]: ../clients/bpqaprs.md
[hostmode]: ../protocols/host-mode.md

## Minimum viable cfg

The cfg file format is identical across platforms — see the
[Configuration reference][cfg].  A minimum Windows-side `bpq32.cfg`:

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

[cfg]: ../configuration/reference.md

Save as `%appdata%\BPQ32\bpq32.cfg` and start BPQ32.exe — a
console window opens with the same banner you'd see from
`linbpq` on Linux.

## Common Windows-side companions

These are amateur-radio applications people commonly run *with*
BPQ32 on Windows:

| App | How it talks to BPQ32 |
|---|---|
| **AGWPE** | BPQ32 has a built-in AGW emulator (`AGWPORT=`); AGWPE-client apps connect directly. |
| **AR-Cluster v6** | Uses the AGW interface. |
| **CC Cluster** | Telnet, with a `CMDPORT=` declared in `bpq32.cfg`. |
| **DXSpider** | DLL or AGWtoBPQ interface. |
| **RMS Packet** | Direct `BPQ32.DLL` interface. |
| **WinFBB** (701A / 700I) | Direct DLL or `TFWIN.DLL`. |
| **UI-DX Bridge** | AGWPE interface. |

These are the classical Windows-only companions.  Most of them
have either Linux replacements or talk one of the wire protocols
LinBPQ already speaks (telnet, AGW, BPQHostModes), so you can
mix and match across machines.

## Auto-start

Drop a shortcut to `BPQ32.exe` in
`Start Menu\Programs\Startup`, or use a delay-and-sequence tool
like R2 Studio's Startup Delayer if you need ordered starts.

The console can be minimised with **Action → Start Minimized**
or **Action → Minimize to Notification Area**; pre-built
shortcuts in both styles ship in the installer's `shortcuts`
folder.

## When you'd run both sides

The most common reason to run BPQ32 alongside LinBPQ is to use
a Windows-only modem TNC or driver from the same operator
position — e.g. VARA HF on its native Windows runtime, or a
piece of Windows-only hardware support.  In that case the two
sides talk over AX/IP-UDP (see the [AX/IP page][axip]),
NET/ROM-over-TCP, or the AGW emulator.  Pick whichever best
matches the link characteristics.

[axip]: ../protocols/axip.md
