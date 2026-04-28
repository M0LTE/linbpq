# APRS gateway

LinBPQ's APRS support has two halves:

- An **APRS digi/iGate** that runs in-process — receives APRS UI
  frames on AX.25 ports, decides whether to digipeat or drop them,
  optionally bridges to APRS-IS, and emits its own beacons, status
  and object reports.
- A **GPS / position source** for the digi's own beacon — either
  fixed `LAT=` / `LON=` values, or live NMEA from a serial GPS.

The optional Windows-side BPQAPRS.exe map client is a *separate
program* that talks to the BPQAPRS API; it has no Linux equivalent
shipped with linbpq today.  Use [QtBPQAPRS][qtbpqaprs] or any
generic APRS-IS client (YAAC, Xastir) instead.

[qtbpqaprs]: https://github.com/G8BPQ/QtBPQAPRS

!!! note "Upstream and source"
    Re-presentation of John Wiseman's [APRS Digipeater/IGate][upstream]
    page.  Cross-checked against `APRSCode.c` (cfg parsing,
    digipeat decision, IS uplink, beacon scheduling) and
    `tests/integration/test_aprs.py` (block parsing, STATUS / SENT /
    MSGS / BEACON commands, outbound APRS-IS connect to a fake
    server, OBJECT timer).

[upstream]: https://www.cantab.net/users/john.wiseman/Documents/APRSDigiGate.html

## Quick example

```ini
APRSDIGI
 APRSCALL=N0CALL-10
 SYMBOL=a
 SYMSET=B
 STATUSMSG=BPQ32 iGate
 LAT=5828.50N
 LON=00612.70W

 ; per-port outbound path
 APRSPath 1=APRS,WIDE1-1,WIDE2-1
 APRSPath 2=                    ; receive-only on port 2

 BeaconInterval=30
 MobileBeaconInterval=2

 ; New-N digipeating
 TraceCalls=WIDE,TRACE
 FloodCalls=GBR
 DigiCalls=SKIG
 ReplaceDigiCalls
 MaxTraceHops=2
 MaxFloodHops=2

 ; cross-port digi map
 Digimap 1=1,IS                 ; port 1 packets repeat on port 1, gate to APRS-IS
 Digimap 2=                     ; port 2 doesn't digi anywhere

 ; APRS-IS uplink
 ISHost=england.aprs2.net
 ISPort=14580
 ISPasscode=12345
 ISFilter=m/50
***
```

The block ends with `***` (three asterisks).  The `APRSDIGI` block
is a top-level cfg fragment, parallel to `PORT` and `IPGATEWAY`.

## Identity

| Keyword | Effect |
|---|---|
| `APRSCALL=<call>` | Source call for everything the digi originates.  Defaults to `NODECALL` if absent. |
| `STATUSMSG=<text>` | Free-form status text included in periodic status beacons. |
| `SYMBOL=<char>` | APRS symbol code (e.g. `a` for ambulance, `>` for car).  See the [APRS symbol reference][symbols]. |
| `SYMSET=<char>` | Symbol *set* — usually `/` (primary) or `\` (alternate); `B` selects the overlay-B variant. |

[symbols]: http://www.aprs.org/symbols.html

## Position source

Either fixed coordinates:

```
LAT=5828.50N        ; ddmm.mmN/S
LON=00612.70W       ; dddmm.mmE/W
```

…or a live GPS:

```
GPSPort=/dev/ttyUSB0
GPSSpeed=4800
```

If both are present GPS wins.  The digi reads NMEA `$GPRMC` /
`$GPGGA` sentences and updates the beacon position from each fix.

## Per-port path

`APRSPath <portnum>=<dest>,<digi1>,<digi2>...` controls the
unproto path for traffic *originated* on a port (beacons,
status, gated traffic).

| Form | Meaning |
|---|---|
| `APRSPath 1=APRS,WIDE1-1,WIDE2-1` | Standard "WIDE1-1,WIDE2-1" routing through paths. |
| `APRSPath 1=` | Receive-only — never originate on this port. |
| Destination `APRS` | Rewritten to `APBPQ1` (the BPQ32 software ID).  Use `APRS-0` to send the literal string `APRS`. |

`GATEDPATH` overrides `APRSPath` when gating traffic *down*
from APRS-IS to RF.

## New-N digipeating

LinBPQ implements the New Paradigm scheme — UI frames whose
digipeater list contains `WIDEn-N` aliases get processed by
counting down `N` and (optionally) replacing the wide-call with
the digi's own call:

| Keyword | Effect |
|---|---|
| `TraceCalls=<list>` | Comma-separated calls handled with *trace* — the digi inserts its own call into the path.  Standard list is `WIDE,TRACE`. |
| `FloodCalls=<list>` | Calls handled *without* trace — call kept verbatim, only the SSID counts down.  Typical: regional aliases like `GBR`, `EU`. |
| `DigiCalls=<list>` | Plain digi — no SSID manipulation, no trace.  Useful for fill-in digis on local aliases like `SKIG`. |
| `ReplaceDigiCalls` | Replace the matched call with `APRSCALL` rather than leave it intact.  Most operators want this on. |
| `MaxTraceHops=<n>` | Cap inbound `WIDEn-N` to `n` regardless of what arrived (`WIDE7-7` becomes `WIDE7-2` if `MaxTraceHops=2`). |
| `MaxFloodHops=<n>` | Same cap for flood-call SSIDs. |

## Cross-port routing

```
Digimap 1=2,IS         ; port 1 repeats on 2, gates to APRS-IS
Digimap 2=1,2,IS       ; port 2 repeats on 1 and 2, gates to APRS-IS
Digimap 7=             ; port 7 is receive-only at the cross-port stage
```

`Digimap` overrides the default ("repeat on receive port + gate
to IS").  `IS` is the special token for the APRS-IS gateway
(see below).

`BRIDGE n=m` (in the main bpq32.cfg, not the APRSDIGI block)
copies *every* L2 frame on port n verbatim to port m without
running the APRS digi logic — useful for socat-bridging a virtual
serial port to an external APRS client.

## Beacons, objects, weather

```
BeaconInterval=30          ; minutes when stationary (min 5)
MobileBeaconInterval=2     ; minutes while GPS reports motion
BeacontoIS=1               ; also send our own beacons up to APRS-IS

OBJECT PATH=APRS,WIDE1-1 PORT=1,IS INTERVAL=30 TEXT=;444.80BPQ\*111111z5807.60N/00610.63Wr%156 R15m
```

Object format notes:

- Single space between fields, no spaces inside `PATH=` /
  `PORT=` / `INTERVAL=` / `TEXT=`.
- `PORT=` accepts the same destination tokens as `Digimap`,
  including `IS`.
- `INTERVAL=` minutes; minimum is 10.[^object-min]

[^object-min]: From `APRSCode.c:1811`: `Timer = ObjectCount * 10
    + 30` — first beacon ~30 s after boot, then `INTERVAL`-minutes
    cadence.  Locked in by
    `test_long_runtime_aprs_object.py`.

Weather beacons (UI-View `wxnow.txt` format):

```
WXFileName=/var/lib/aprs/wxnow.txt
WXInterval=10
WXPortList=1,IS
WXComment=BPQ Weather
```

## APRS-IS uplink

| Keyword | Effect |
|---|---|
| `ISHost=<host>` | APRS-IS server.  Pick a regional one; `england.aprs2.net`, `noam.aprs2.net`, `rotate.aprs2.net`. |
| `ISPort=<port>` | Server port.  `14580` is the standard filtered-feed port. |
| `ISPasscode=<n>` | Authentication passcode for `APRSCALL`.  Required for *uploading* to APRS-IS; receive-only iGates can leave it blank. |
| `ISFilter=<filter>` | Initial server-side filter expression.  See [APRS-IS filter docs][filters].  Example: `m/50` for stations within 50 km. |
| `RXONLY=1` | Receive-only iGate — never push from RF to IS. |
| `SATGATE=1` | Defer direct-RF copies to APRS-IS so satellite-received copies (which arrive seconds later) take priority. |
| `BeacontoIS=0/1` | Whether the digi's own beacons / status / objects also go to APRS-IS. |
| `LOGAPRSIS=0/1` | Verbose logging of APRS-IS exchange (writes to `logs/`). |
| `GateLocalDistance=<miles>` | Re-radiate IS traffic for stations within this radius down to RF.  Use carefully — it's easy to drown a quiet RF channel in IS chatter. |

[filters]: http://www.aprs-is.net/javAPRSFilter.aspx

## Memory and station storage

| Keyword | Effect |
|---|---|
| `MaxStations=<n>` | Cap on retained station records (default 500).  A full APRS-IS feed is ~20k stations; raising this raises memory use roughly linearly. |
| `MaxAge=<minutes>` | Drop a station if no traffic seen for this long. |
| `SaveAPRSMsgs=1` | Persist the message store across reboots. |

## Display options

| Keyword | Effect |
|---|---|
| `LOCALTIME` | Show local time instead of UTC in any rendered output (web pages, BPQAPRS API). |
| `DISTKM` | Distance display in km rather than miles. |

## Node-prompt commands

These run from the LinBPQ telnet node prompt when an APRSDIGI
block is configured:

| Command | Effect |
|---|---|
| `APRS STATUS` | Last-heard status / position from each tracked station. |
| `APRS SENT` | Recently-transmitted UI frames (beacons, status, etc). |
| `APRS MSGS` | Stored APRS messages received and pending acknowledgement. |
| `APRS BEACON` | Send a position beacon now without waiting for the timer. |

## Test coverage

| Test file | What it locks in |
|---|---|
| [`test_aprs.py`][t-aprs] | APRSDIGI block parsing, `APRS STATUS` / `SENT` / `MSGS` / `BEACON` node commands, outbound APRS-IS connect against a fake server |
| [`test_long_runtime_aprs_object.py`][t-obj] | Single-OBJECT line emits its first UI beacon at ~30 s with the expected body and AX.25 destination `APBPQ1` |

[t-aprs]: https://github.com/M0LTE/linbpq/blob/master/tests/integration/test_aprs.py
[t-obj]: https://github.com/M0LTE/linbpq/blob/master/tests/integration/test_long_runtime_aprs_object.py
