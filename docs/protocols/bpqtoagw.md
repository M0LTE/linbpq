# BPQtoAGW

The `BPQtoAGW` driver lets LinBPQ talk to any soundcard modem
that exposes an [AGW protocol][agw] socket — Direwolf, SoundModem
(UZ7HO), AGWPE, etc.  From AX.25's perspective the modem is a
KISS TNC and LinBPQ does all the L2 timing; the AGW socket just
carries frames in and out.

[agw]: https://www.sv2agw.com/Home/AGWPacketEngine

!!! note "Upstream and source"
    Re-presentation of John Wiseman's [BPQtoAGW][upstream] page.
    Driver source: [`BPQtoAGW.c`][src].

[upstream]: https://www.cantab.net/users/john.wiseman/Documents/BPQtoAGW.htm
[src]: https://github.com/M0LTE/linbpq/blob/master/BPQtoAGW.c

## Quick example

```ini
PORT
 PORTNUM=2
 ID=AGWPE Port 1 (left soundcard)
 TYPE=EXTERNAL
 DRIVER=BPQtoAGW
 IOADDR=1F40        ; 8000 decimal — AGW default
 CHANNEL=A          ; A => AGW port 1, B => AGW port 2, ...
 QUALITY=192
 MAXFRAME=7
 FRACK=1000
 RESPTIME=250
 RETRIES=10
 PACLEN=236
 CONFIG
 ; (optional) remote AGW host
 hostname.example.com 8000
ENDPORT
```

## CONFIG line

The `CONFIG` block holds at most one line:

```
<host> <port> [<user> [<password>]]
```

| Field | Meaning |
|---|---|
| `<host>` | AGW server hostname / IP.  Defaults to `127.0.0.1`. |
| `<port>` | AGW TCP port.  Defaults to the `IOADDR` value (decimal hex → integer). |
| `<user>` `<password>` | Optional credentials for AGW servers that require auth. |

If the AGW server is local and on the default port, you can leave
the CONFIG line empty (or omit `CONFIG ... ENDPORT` entirely).

## Per-port keywords

| Keyword | Effect |
|---|---|
| `IOADDR=<hex>` | AGW server TCP port, expressed in hexadecimal.  `1F40` = 8000 (the AGW default), `1F41` = 8001. |
| `CHANNEL=<A..>` | Which AGW port-letter this BPQ port maps to. |

`MAXFRAME` / `FRACK` / `RESPTIME` / `RETRIES` / `PACLEN` /
`QUALITY` and friends are the standard PORT-block knobs — see
the [Configuration reference][cfg].

[cfg]: ../configuration/reference.md

## Multiple AGW ports

One AGW server typically exposes 2+ "ports" (one per soundcard
channel).  Declare a separate LinBPQ `PORT` block for each, using
the same `IOADDR` (and CONFIG host) and a different `CHANNEL`:

```ini
PORT
 PORTNUM=2
 ID=AGW left
 TYPE=EXTERNAL
 DRIVER=BPQtoAGW
 IOADDR=1F40
 CHANNEL=A
 ; ...
ENDPORT

PORT
 PORTNUM=3
 ID=AGW right
 TYPE=EXTERNAL
 DRIVER=BPQtoAGW
 IOADDR=1F40
 CHANNEL=B
 ; ...
ENDPORT
```

## Notes

- `PACLEN=236` is the practical maximum — NET/ROM frames over
  AX.25 can't exceed 236 bytes without fragmentation.
- `QUALITY=0` parks the port at L2 only — no NODES propagation
  uses it.
- The AGW server (Direwolf, SoundModem etc.) is responsible for
  modem-level timing (TXDELAY, persistence) inside the AGW
  configuration — `TXDELAY=` etc. on the BPQ side are ignored
  for this driver because BPQ never speaks KISS framing parameters
  over the AGW wire.
