# BPQ Host Mode Emulator (BPQHostModes)

`BPQHostModes` is a separate Windows program that lets legacy
TNC-driving software (Airmail, Paclink, RMS Express, Winlink
Classic, Winpack) talk to a BPQ node by pretending to be a
hardware TNC2 in Kantronics or WA8DED host mode.  On Windows it's
useful when those programs don't speak the BPQ Virtual COM Port
driver natively; on Linux it's only relevant under Wine.

LinBPQ itself doesn't ship `BPQHostModes` as part of the Linux
build — but a connected client that *uses* it lands at LinBPQ
through the same TNC-emulator surface (`TNCPORT` blocks in
`bpq32.cfg`) as a directly-connected serial program would.

!!! note "Upstream and source"
    Re-presentation of John Wiseman's
    [BPQ Host Mode Emulator][upstream] page.  Windows program;
    Linux relevance is via Wine.

[upstream]: https://www.cantab.net/users/john.wiseman/Documents/BPQ%20Host%20Mode%20Emulator.htm

## Protocol modes

| Mode | Compatible with |
|---|---|
| **Kantronics** | Airmail (dual-port for client/server), Paclink, RMS Packet (with caveats), most pre-2010 packet apps |
| **DED (WA8DED) host mode** | RMS Express in Robust-Packet mode, Winlink Classic, Winpack |

Pick the mode the client actually expects — the wire formats are
different and not interoperable.

## When you'd use it

- You're running an old packet-radio program under Wine that
  expects a serial-port TNC.
- The program speaks one of the host-mode protocols above.
- LinBPQ is the back end you want it to talk to.

If you control the application stack and can use the [LinBPQ
Apps Interface][cmdport] (`CMDPORT=`) instead, that's a better
fit — same end result, no Wine.

[cmdport]: ../configuration/reference.md

## Workflow on the LinBPQ side

Whatever drives the host-mode program (Airmail / Wine / direct
Windows host) needs to land on a serial-shaped surface that the
BPQ side can speak host-mode at.  In LinBPQ that's a
[`TNCPORT`][tncport] block — a virtual TNC that exposes a PTY,
runs Kantronics / DED / TNC2 / SCS host mode, and binds to one
of your `APPLICATION` slots:

[tncport]: ../configuration/reference.md

```ini
TNCPORT
 COMPORT=/dev/ttyS5    ; LinBPQ creates a PTY, this is the slave name
 TYPE=DED
 APPLFLAGS=6
 APPLNUM=1             ; bind to BBS app slot
 CHANNELS=4
ENDPORT
```

The Wine-hosted program opens `/dev/ttyS5` (mapped through the
Wine COM-port machinery) and gets host-mode framing on the wire.

## TNCPORT keywords

| Keyword | Effect |
|---|---|
| `COMPORT=<path>` | Slave end of the PTY pair LinBPQ creates. |
| `TYPE=<TNC2/DED/KANT/SCS>` | Host-mode protocol to emulate. |
| `APPLNUM=<n>` | Which APPLICATION slot this TNC delivers traffic to. |
| `APPLMASK=<hex>` | Alternative bitmask form. |
| `APPLFLAGS=<n>` | Sum of: `1` (pass cmds to app), `2` (CONNECTED to user), `4` (CONNECTED to app), `8` (`^D` = disconnect). |
| `CHANNELS=<n>` | Concurrent host-mode channels.  TNC2 only supports 1; DED / KAM / SCS allow up to ~16. |
| `POLLDELAY=<ms>` | Throttle BPQ-VCOM polling — Windows-only. |

## Comments

The program is showing its age — most modern packet apps either
speak AGW directly (in which case point them at the AGW
emulator), or talk telnet (in which case point them at the
Telnet driver), neither of which needs the host-mode shim.
Reach for `BPQHostModes` only when the application leaves you
no choice.
