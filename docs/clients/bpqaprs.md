# BPQAPRS — APRS map and messaging client

`BPQAPRS.exe` is a Windows desktop application that pairs with
the BPQ32 [APRS digi/iGate][digi] subsystem to provide an
interactive map and APRS messaging interface.  It runs on the
same machine as BPQ32 and uses the in-process BPQAPRS API for
station data and outbound transmissions.

A more recent cross-platform alternative is [QtBPQAPRS][qt],
written by John in Qt — this is the right starting point on
Linux.

[digi]: ../subsystems/aprs.md
[qt]: https://github.com/G8BPQ/QtBPQAPRS

!!! note "Platform"
    `BPQAPRS.exe` itself is **Windows-only**.  On Linux use
    QtBPQAPRS, [Xastir][xastir], [YAAC][yaac], or any APRS-IS
    client of your choice — they all talk to APRS-IS rather
    than the BPQ32 in-process API, but most users won't notice
    the difference.

[xastir]: https://xastir.org/
[yaac]: https://www.ka2ddo.org/ka2ddo/YAAC.html

!!! note "Upstream"
    Re-presentation of John Wiseman's [BPQ APRS][upstream] page.

[upstream]: https://www.cantab.net/users/john.wiseman/Documents/BPQAPRS.htm

## What it does

- **Map**: OpenStreetMap-tile map with mouse-wheel zoom, drag
  to pan, click stations for details, station tracks rendered
  as configurable colour trails.
- **Station list**: every station BPQAPRS has heard, sorted by
  last-heard, distance, callsign or icon type.  Double-click a
  station to centre the map on it.
- **Messaging**: send / receive APRS messages from the same
  pane as the map.  Configurable retry interval and ack handling.
- **Status broadcast**: send your own position and status into
  APRS-IS and over RF.

## Connecting it to BPQ32

BPQAPRS doesn't need any configuration on the BPQ32 side
beyond the `APRSDIGI` block — the two communicate via the
BPQAPRS API hosted by `bpq32.dll`.

The optional `RUN BPQAPRS.exe` line in the `APRSDIGI` block
auto-launches the client when BPQ32 starts:

```ini
APRSDIGI
 RUN BPQAPRS.exe
 APRSCALL=N0CALL-10
 ; ... rest of APRSDIGI config ...
***
```

## Filtering

BPQAPRS uses the standard APRS-IS filter syntax for the
incoming feed.  An example useful for testing — show stations
within 50 km, only ones broadcasting `APBPQ*` software ID:

```
m/50 u/APBPQ*
```

When BPQAPRS is running, its filter overrides any `ISFILTER=`
in the `APRSDIGI` block; close the client and the digi reverts
to the cfg filter.

## Snapshot output

BPQAPRS can write a periodic JPEG snapshot of the current map
view, suitable for dropping onto a club website that wants
"live local APRS activity" without doing the rendering itself.
Configure interval and output file in BPQAPRS's options dialog.

## Display options

These map onto the same cfg keywords as the digi side:

- `LOCALTIME` — show local time rather than UTC.
- `DISTKM` — distances in km rather than miles.

Set them in `bpq32.cfg`'s `APRSDIGI` block; BPQAPRS picks them
up via the API.

## Map clients alternatives summary

| Client | Platform | Talks to |
|---|---|---|
| BPQAPRS.exe | Windows | BPQ32 (in-process API) |
| [QtBPQAPRS][qt] | Linux + Windows + macOS | BPQAPRS API or APRS-IS |
| [Xastir][xastir] | Linux + macOS | AGW interface, KISS, APRS-IS |
| [YAAC][yaac] | Linux + Windows + macOS | AGW interface, KISS, APRS-IS |
| Pinpoint, APRSIS32, etc. | Various | APRS-IS |

If you're standing up a new mapping client today on Linux,
QtBPQAPRS or Xastir are the right starting points.
