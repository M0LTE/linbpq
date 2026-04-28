# RHP (Remote Host Protocol)

Paula Dowley G8PZT's *Remote Host Protocol* is a JSON-over-
WebSocket session-management protocol, originally designed for
[XRouter][xrouter].  LinBPQ ships a minimal implementation of
the same wire format, sufficient to support
[WhatsPac][whatspac] (the WhatsApp ↔ packet bridge by John
Wiseman G8BPQ).

This is a niche interface — WhatsPac is essentially the only
known consumer.  If you're not building a WhatsPac-shaped tool
and the [Apps Interface][apps] or the AGW emulator give you
what you need, you almost certainly want one of those instead.

[xrouter]: http://www.xrouter.org.uk/
[whatspac]: https://github.com/g8bpq/WhatsPac
[apps]: apps-interface.md

!!! note "Source and references"
    Cross-checked against `RHP.c` and `HTTPcode.c` in the LinBPQ
    source.  The original protocol white paper is in the
    [OARC packet white-papers wiki][oarc] (Paula's PDFs).
    LinBPQ does *not* implement the full protocol — only the
    subset WhatsPac needs.

[oarc]: https://wiki.oarc.uk/packet:white-papers

## Transport

RHP messages travel as UTF-8 JSON inside WebSocket frames,
carried over the BPQ HTTPPORT:

```
ws://<host>:<HTTPPORT>/rhp
```

Standard WebSocket upgrade — `Upgrade: websocket` /
`Sec-WebSocket-Key:` headers — and BPQ replies with `101
Switching Protocols`.  Each WebSocket frame carries exactly
one JSON object.

The `/rhp` endpoint is unauthenticated; access control is by
network reachability of the HTTP listener.  Bind HTTPPORT to
loopback (or restrict via `LOCALNET`) if you don't want
anonymous RHP clients hitting the node.

## Identifiers

Three distinct numeric IDs flow through the JSON:

| Field | Meaning |
|---|---|
| `id` | Request correlation.  Set by the client on each control message; the matching reply echoes the same `id` back. |
| `handle` | Session identity.  Returned in `openReply` and used on every subsequent `send` / `recv` / `status` / `close` for that session. |
| `seqno` | Server-assigned sequence number, incremented on every server-initiated message *to* a session (e.g. each `recv`, status change, far-end close). |

A single WebSocket connection can carry multiple concurrent
sessions, distinguished by `handle`.

## Messages

### `open` — start a session

Client → server:

```json
{"type":"open","id":5,"pfam":"ax25","mode":"stream",
 "port":"1","local":"G8BPQ","remote":"G8BPQ-2","flags":128}
```

| Field | Notes |
|---|---|
| `pfam` | Protocol family.  **Must be `ax25`** — LinBPQ rejects anything else with `errCode: 12 ("Bad parameter")`. |
| `mode` | **Must be `stream`** — datagram / UI / KISS modes that XRouter offers are not implemented. |
| `port` | BPQ port number to originate the connection on. |
| `local` | Source callsign, ≤ 10 chars. |
| `remote` | Destination callsign, ≤ 10 chars. |
| `flags` | Parsed but **ignored** by LinBPQ.  Set to whatever your client library defaults to. |

Server → client:

```json
{"type":"openReply","id":5,"handle":1,"errCode":0,"errText":"Ok"}
```

`errCode` 0 means the session is allocated and the underlying
NET/ROM connect attempt is in flight; the actual transport
result arrives later as a `status` message (see below).

### `status` — connection state changes

The server pushes an unsolicited `status` message on every
state transition.  Two values matter for an opened session:

| Flags | Meaning |
|---|---|
| `0` | Initial — session opened, NET/ROM connect in progress. |
| `2` | Connected to remote.  The session is now usable. |

```json
{"seqno":0,"type":"status","handle":1,"flags":2}
```

A client can also poll with `{"type":"status","handle":N}`;
LinBPQ replies with `{"type":"statusReply","handle":N,"flags":2}`
or an `errcode: 3` if the handle isn't valid.

After a successful connect LinBPQ emits a synthetic banner as
a `recv`:

```json
{"seqno":1,"type":"recv","handle":1,"data":"Connected to RHP Server\r"}
```

### `send` — outbound bytes

Client → server:

```json
{"type":"send","id":70,"handle":1,"data":";;;;;;\r"}
```

`data` is a JSON string carrying the payload.  Standard
JSON escaping applies — `\r`, `\n`, `\\`, `\"`, `\uXXXX` for
non-ASCII.  Binary bytes above 0x7F are awkward (must be
escaped as UTF-8 sequences and the receiver has to decode them
back); RHP isn't well-suited to truly binary protocols.

Server reply:

```json
{"type":"sendReply","id":70,"handle":1,"errCode":0,"errText":"Ok","status":2}
```

### `recv` — inbound bytes

Server → client (unsolicited):

```json
{"seqno":N,"type":"recv","handle":1,"data":"…"}
```

One `recv` per arriving chunk.  Same JSON-string conventions
for `data` as `send`.

### `close` — tear down a session

Either side can close.  Client → server:

```json
{"id":40,"type":"close","handle":1}
```

Server reply:

```json
{"id":40,"type":"closeReply","handle":1,"errcode":0,"errtext":"Ok"}
```

When the *remote* end disconnects, the server pushes:

```json
{"type":"close","seqno":N,"handle":1}
```

…unsolicited.  Treat it as the session having gone away.

### `keepalive`

Client → server (every ~3 minutes of idle, by convention):

```json
{"type":"keepalive"}
```

Server reply:

```json
{"type":"keepaliveReply"}
```

## Error codes

LinBPQ uses the standard XRouter RHP code table:

| Code | Meaning |
|---|---|
| 0 | Ok |
| 1 | Unspecified |
| 2 | Bad or missing type |
| 3 | Invalid handle |
| 4 | No memory |
| 5 | Bad or missing mode |
| 6 | Invalid local address |
| 7 | Invalid remote address |
| 8 | Bad or missing family |
| 9 | Duplicate socket |
| 10 | No such port |
| 11 | Invalid protocol |
| 12 | Bad parameter |
| 13 | No buffers |
| 14 | Unauthorised |
| 15 | No Route |
| 16 | Operation not supported |

## Limitations vs full RHP / XRouter

The LinBPQ implementation is deliberately minimal.  Things the
full Paula spec covers that LinBPQ doesn't:

- Other protocol families (`netrom` direct, `udp`, `kiss`, etc.)
- Datagram and UI modes (`mode: "datagram"`, `mode: "ui"`)
- Server-initiated *listen* sessions (the LinBPQ side can't
  register a callsign for inbound RHP connects)
- Authentication / login on the WebSocket
- Per-session statistics

If you need any of those, talk to XRouter, not LinBPQ.

## Sysop command

`RHP` at the node prompt prints the active session table:

```
|Stream|Local    |Remote   |Handle| Seq |Busy|
|   3  |G8BPQ    |G8BPQ-2  |   1  |   42| 0  |
```

| Column | Meaning |
|---|---|
| `Stream` | Internal BPQ stream number this RHP session is bound to. |
| `Local` | Source callsign passed in `open`. |
| `Remote` | Destination callsign. |
| `Handle` | RHP handle. |
| `Seq` | Last `seqno` issued on the server-→-client side. |
| `Busy` | Internal flow-control marker. |

The command is a sysop-level read; it doesn't accept
arguments.

## Should you use this?

Almost certainly not, unless:

- You're WhatsPac.
- You're writing a fresh WhatsApp / Matrix / Telegram ↔ packet
  bridge and want compatibility with Paula's protocol family.

For most "I want to drive BPQ from my own program" tasks,
[the Apps Interface][apps] (CMDPORT) or AGW are simpler,
better-documented, and don't require pulling JSON-over-
WebSocket into the design.
