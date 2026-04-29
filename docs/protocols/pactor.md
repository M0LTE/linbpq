# Pactor / WINMOR / ARDOP / VARA

LinBPQ supports a stack of HF connected-mode modems through
controller-specific drivers.  The Pactor family covers hardware
TNCs (Kantronics KAM, AEA / Timewave PK-232, SCS PTC, HAL DXP /
Clover); ARDOP and VARA are software (soundcard) modems with TCP
control sockets; WINMOR is the historical predecessor of ARDOP
(deprecated since ~2017).

This page covers all of them — the workflow is similar enough
that one page is easier to navigate than five.

!!! note "Upstream and source"
    Re-presentation of John Wiseman's [Using Pactor with BPQ32][p-up]
    and [Using WINMOR with BPQ32][w-up] pages.  Drivers cross-checked
    against `KAMPactor.c`, `AEAPactor.c`, `SCSPactor.c`,
    `SCSTracker.c`, `SCSTrackeMulti.c`, `HALDriver.c`,
    `WINMOR.c`, `ARDOP.c`, `VARA.c`.

[p-up]: https://www.cantab.net/users/john.wiseman/Documents/Using%20Pactor.htm
[w-up]: https://www.cantab.net/users/john.wiseman/Documents/Using%20WINMOR.htm

## Driver matrix

| Driver | Hardware / software | Transport | Notes |
|---|---|---|---|
| `KAMPactor` | Kantronics KAM controllers | Serial | Pactor I/II depending on hardware |
| `AEAPactor` | AEA / Timewave PK-232 family | Serial | Pactor I |
| `SCSPactor` | SCS PTC family (DSP-2120, PTC-IIex, PTC-IIIusb) | Serial | Pactor I/II/III/IV |
| `SCSTracker` | SCS Tracker (DSP-4100), single-session | Serial | Robust Packet |
| `TrackeMulti` | SCS Tracker, multi-session | Serial | Same hardware, different host-mode |
| `HALDriver` | HAL Communications DXP-38 / Clover-II | Serial | Clover or Pactor |
| `WINMOR` | Soundcard (deprecated) | TCP | Superseded by ARDOP |
| `ARDOP` | Soundcard (`ardopc`, `ardopcf`) | TCP | Recommended free / open-source HF mode |
| `VARA` | Soundcard (commercial Windows app) | TCP | Two adjacent sockets — control + data |

## Common configuration shape

```ini
PORT
 ID=HF Pactor (PTC-II)
 TYPE=EXTERNAL
 DRIVER=SCSPactor
 QUALITY=10
 MAXFRAME=1
 PACLEN=80
 INTERLOCK=1            ; share PTT with the other HF port
 CONFIG
 ; driver-specific lines
ENDPORT
```

Each driver has its own CONFIG-block keyword set; the shape varies
by hardware.

## ATTACH workflow

Pactor / VARA / ARDOP ports are *attached* before use rather than
auto-listening like packet-VHF ports.  At the node prompt:

```
ATTACH 3
```

| Response | Meaning |
|---|---|
| `OK` | Port allocated; you can drive the TNC directly. |
| `Error - Invalid Port` | Port number is wrong, or it isn't a Pactor / VARA / ARDOP port. |
| `Error - Port in use` | Already attached by someone else.  Wait or use `INTERLOCK` to wait politely. |

Once attached, ordinary node commands work but the underlying
session goes via the HF modem.  `D` to disconnect; ordinary `C`
to connect to a peer.

A connected-script BBS forwarding example:

```
"ATT 3"
"C N0BBB"
"BBS"
```

## Driver-specific keywords

!!! note "Serial drivers: COMPORT and SPEED are PORT-level"
    For all the serial drivers below (KAM, AEA, SCS, Tracker,
    HAL), ``COMPORT=`` and ``SPEED=`` belong **inside the
    PORT block but before the CONFIG keyword** — they're parsed
    by the main parser, not the driver's CONFIG-block handler.
    Put them after ``DRIVER=`` and before ``CONFIG``; the
    CONFIG block then carries only the driver-specific
    keywords (or is empty).

### KAMPactor (Kantronics KAM)

Serial-attached.  KAM commands are case-insensitive and identical
in normal and host mode.  CONFIG-block keywords (``KAMPactor.c``):
``DEBUGLOG``, ``APPL <n>`` (bind to APPLICATION slot),
``OLDMODE`` / ``VERYOLDMODE`` (legacy KAM firmware), ``BUSYWAIT``,
``WL2KREPORT`` plus the ``standardParams`` set.

```ini
PORT
 ID=KAM
 TYPE=EXTERNAL
 DRIVER=KAMPACTOR
 COMPORT=/dev/ttyUSB0
 SPEED=9600
 CONFIG
 APPL 1
ENDPORT
```

### AEAPactor (PK-232 family)

Serial.  Init bytes go out within seconds of the port coming up;
``AEAExtInit`` opens the PTY synchronously.  CONFIG-block
keywords: ``APPL`` plus ``standardParams``; the rest of the
init script goes verbatim to the TNC.

```ini
PORT
 ID=PK-232
 TYPE=EXTERNAL
 DRIVER=AEAPACTOR
 COMPORT=/dev/ttyUSB0
 SPEED=4800
 CONFIG
 APPL 1
ENDPORT
```

### SCSPactor (PTC family)

Serial.  Uses DED Host Mode command set — different from the
KAM "AT command" style.  CONFIG-block keywords (``SCSPactor.c``):
``APPL``, ``DEBUGLOG``, ``PACKETCHANNELS``,
``SCANFORROBUSTPACKET``, ``USEAPPLCALLS`` /
``USEAPPLCALLSFORPACTOR``, ``DRAGON``, ``DEFAULT ROBUST`` /
``FORCE ROBUST``, ``DontAddPDUPLEX``, plus ``standardParams``.

```ini
PORT
 ID=PTC-II
 TYPE=EXTERNAL
 DRIVER=SCSPACTOR
 COMPORT=/dev/ttyUSB0
 SPEED=57600
 CONFIG
 APPL 1
 DEFAULT ROBUST
ENDPORT
```

### SCSTracker / TrackeMulti

The same DSP-4100 hardware.  Pick the driver based on whether
you want one session at a time (``SCSTracker``) or multiple
(``TrackeMulti``).

```ini
PORT
 ID=Tracker
 TYPE=EXTERNAL
 DRIVER=SCSTRACKER
 COMPORT=/dev/ttyUSB0
 SPEED=38400
 CONFIG
ENDPORT
```

### HALDriver

Clover or Pactor mode on HAL Communications hardware.  Older
gear, rare in 2026.  CONFIG-block keywords (``HALDriver.c``):
``APPL``, ``WL2KREPORT``, ``NEEDXONXOFF``, ``TONES``,
``DEFAULTMODE <CLOVER|PACTOR|AMTOR>``, plus ``standardParams``.

```ini
PORT
 ID=HAL
 TYPE=EXTERNAL
 DRIVER=HALDRIVER
 COMPORT=/dev/ttyUSB0
 SPEED=4800
 CONFIG
 DEFAULTMODE CLOVER
ENDPORT
```

### WINMOR (deprecated)

Two TCP sockets — control + data — on adjacent ports (default
8500 and 8501).  WINMOR has been deprecated for ARDOP since
~2017; you almost certainly want `ARDOP` not `WINMOR` on a new
build.

```
CONFIG
ADDR 127.0.0.1 8500 PATH /usr/local/bin/wine WINMOR_TNC.exe
BUSYHOLD 5
SESSIONTIMELIMIT 60
```

### ARDOP

Same wire shape as WINMOR / VARA — a TCP TNC.  Use [ardopcf][ardopcf]
(open-source, builds on Linux) or commercial ARDOPC.

[ardopcf]: https://github.com/pflarue/ardop

```
CONFIG
ADDR 127.0.0.1 8515
BW 500
LISTEN TRUE
```

The init script after socket-up sends `LISTEN TRUE`, telling the
TNC to accept inbound calls.  (For VARA the equivalent is `LISTEN ON`.)

### VARA

Commercial soundcard modem.  Two TCP sockets (port + port+1) —
the control socket and the data socket.  Runs as a Windows
program; on Linux you'll typically run it under Wine.

```
CONFIG
ADDR 127.0.0.1 8300
MYCALL N0CALL
LISTEN ON
BW2300                 ; or BW500 / BW1000
```

`BW2300` and similar bandwidth keywords are forwarded to VARA
verbatim — VARA's keyword set evolves, so check its current
docs for what's accepted.

## Multiple HF ports on one radio

Pactor + WINMOR sharing one transceiver is the classic "one
radio, several modes" setup.  Use `INTERLOCK` so the two ports
don't try to TX simultaneously:

```ini
PORT
 ID=Pactor
 INTERLOCK=1
 ; ...
ENDPORT

PORT
 ID=ARDOP
 INTERLOCK=1
 ; ...
ENDPORT
```

Both share group 1; whichever attaches first gets the radio,
the other waits.

## Status windows

Each Pactor-family driver exposes a status block at the node
prompt:

| Command | Effect |
|---|---|
| `RADIO <port>` | Print the modem's status line / connection state. |
| `RIGRECONFIG` | Reload the RIGCONTROL block (frequency / mode tables). |
| `RESTARTTNC <port>` | Cycle the port — close the session, reopen the serial / TCP, send init again. |

## Rig control

`RIGCONTROL ... ENDPORT` blocks couple a port to a CAT-controlled
rig, so a `RADIO 7.080 USB <port>` directive in a forwarding script
can retune the radio before dialling out.  This is its own
feature; covered in detail in the upstream
[RigControl][rig-up] page.

[rig-up]: https://www.cantab.net/users/john.wiseman/Documents/RigControl.htm

## Airmail / Paclink integration on Linux

The classic upstream guide for using Airmail with WINMOR is
Windows-specific (uses VCOMConfig virtual COM ports and the
Windows-only Airmail GUI).  On Linux the equivalent is to use
[Pat winlink-go][pat] talking to LinBPQ over the Telnet driver
or directly via ARDOP / VARA — it's a different software stack
that arrives at the same place.

[pat]: https://getpat.io/

## Incoming-call routing limitation

A single Pactor TNC can route inbound calls to *one* of:

- The node command handler.
- Exactly one application (typically the BBS).

You can't have inbound Pactor ring both the node prompt and the
BBS prompt selectively based on call SSID — that's a hardware-host-mode
constraint, not a LinBPQ thing.  If you need both, run two
Pactor controllers or use ARDOP/VARA which don't have this
limitation.
