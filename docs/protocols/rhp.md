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
    source, plus Paula's RHP v2 white papers — primarily
    [PWP 222 — Remote Host Protocol Version 2][pwp222] and
    [PWP 245 — RHP Version 2 — AX25 Functionality][pwp245],
    indexed at the [OARC packet white-papers wiki][oarc].
    LinBPQ implements a deliberately small subset of RHP v2;
    the rest of the spec is documented in those PDFs and is
    available in XRouter.

[pwp222]: https://wiki.oarc.uk/_media/packet:white-papers:pwp222_remote_host_protocol_version_2.pdf
[pwp245]: https://wiki.oarc.uk/_media/packet:white-papers:pwp245_rhp_version_2_-_ax25_functionality.txt.pdf
[oarc]: https://wiki.oarc.uk/packet:white-papers:index

## What LinBPQ implements vs what RHP v2 defines

The full RHP v2 spec is comparatively rich — multi-protocol
sockets, BSD-style socket-call message family, listen / accept
for inbound, authentication, packet tracing.  LinBPQ implements
only the slice WhatsPac uses.  Side-by-side:

| Area | RHP v2 spec | LinBPQ implementation |
|---|---|---|
| Transport | Raw TCP framed by 2-byte length on port 9000 (default), *or* WebSocket at `ws://host:9000/rhp` | WebSocket only, on the BPQ HTTPPORT.  No raw-TCP RHP listener. |
| Protocol families | `unix`, `inet`, `ax25`, `netrom` | `ax25` only.  Anything else gets `errCode: 12 ("Bad parameter")`. |
| Socket modes | `stream`, `dgram`, `seqpkt`, `custom`, `semiraw`, `trace`, `raw` | `stream` only. |
| `flags` field on `open` | 0x00 passive, 0x01/0x02/0x04 trace flags, 0x80 active | Parsed and ignored — every `open` is treated as an active stream connect. |
| `AUTH` / `authReply` | Required for clients on public IPs not whitelisted in `ACCESS.SYS` | Not implemented.  No authentication on `/rhp`. |
| Listen / `ACCEPT` | Listener sockets register a local callsign; the server pushes `accept` for each inbound connect | Not implemented.  LinBPQ-side RHP can only originate. |
| BSD-style messages: `SOCKET`, `BIND`, `LISTEN`, `CONNECT`, `SENDTO` and replies | Defined as an alternative to the all-in-one `OPEN` | Not implemented; `OPEN` is the only entry point. |
| Client-initiated `STATUS` request | Defined; server replies with `statusReply` (or `status` on success) | Implemented. |
| Address formats (`local`, `remote`) | AX25: `call[-ssid]`; NETROM: `usercall[@nodecall][:svcnum]`; INET: `addr[:port]` | AX25-style only (≤10 chars). |

If you need anything beyond an outgoing AX.25 stream
connection, you're hitting the limits of the LinBPQ
implementation.  XRouter is the reference implementation that
exercises the rest of the spec.

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

`keepalive` doesn't appear in the published RHP v2 spec
(PWP 222 / 245).  Treat it as an XRouter / LinBPQ extension —
both sides honour it, but a strictly-spec-only client wouldn't
emit one and a strictly-spec-only server wouldn't recognise it.
Worth using against LinBPQ: an idle WebSocket otherwise risks
being closed by an intervening proxy.

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

## Implementation quirks

A few rough edges to watch for when writing a strict RHP v2
client and pointing it at LinBPQ:

- **Field-name case is inconsistent.**  PWP 222 / 245 use
  lowercase `errcode` / `errtext` throughout.  LinBPQ emits
  capital-cased `errCode` / `errText` in some replies
  (`openReply`, `sendReply`'s success path) and the spec-correct
  lowercase form in others (`closeReply`, `statusReply` failure).
  Parse case-insensitively if you can.
- **Initial `recv` banner.**  LinBPQ pushes a synthetic
  `{"data":"Connected to RHP Server\r"}` immediately after the
  `flags: 2` status — this isn't in the spec and isn't generated
  by XRouter.  Filter it on the client if it gets in your way.
- **Unrecognised messages are dropped silently** (logged on the
  server side as `Unrecognised RHP Message` but no error reply).
  Don't rely on `errCode: 2 ("Bad or missing type")` to surface a
  malformed message — you'll get nothing back.

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
