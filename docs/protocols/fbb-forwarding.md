# FBB forwarding protocol

FBB is the protocol BBSes use to forward mail and bulletins
between each other.  It runs on top of any L2 transport
(connected-mode AX.25, NET/ROM, AX/IP, plain TCP) — once a
session is up, the two BBSes exchange a SID, swap proposals,
and shovel messages either as plain text (FA) or as compressed
binary blobs (FB / FC = "B1" / "B2").

This page describes the wire protocol.  For configuring a partner
on the LinBPQ side, see [Inter-BBS forwarding][bbs-fwd].

[bbs-fwd]: ../subsystems/bbs-forwarding.md

!!! note "Spec"
    The canonical reference for the protocol is the
    [FBB forwarding protocol spec][spec] (mirrored at
    `packethacking/ax25spec`).  LinBPQ implements it; this page
    summarises the parts that matter for interop.

[spec]: https://github.com/packethacking/ax25spec/blob/main/doc/fbb-forwarding-protocol.md

## Session shape

```
client  →  server : connect
server  →  client : welcome banner, then SID  e.g.  [BPQMail-6.0.25.23-B1FHM$]
client  →  server : SID                                 [BPQMail-6.0.25.23-B1FHM$]
                    ───── either side may now send ─────

client  →  server : FB P MID FROM TO @BBS SIZE  (proposal)
server  →  client : FS Y                        (accept)
client  →  server : (B1-compressed body)
                  : (more proposals, more bodies)

  …or…

client  →  server : FA Title BODY  /EX           (text-mode message)
server  →  client : (no FS framing — text mode just delivers)

  …or…

client  →  server : FF                            (no traffic queued)
server  →  client : FQ                            (terminate session)
client  →  server : (closes)
```

The handshake either side opens with a SID enclosed in `[...]`.
SID format:

```
[<system>-<version>-<flags>]
```

Flags are letters: `F` = supports FBB-style proposals, `B` = B0
(text+RLE), `1` = B1 (compressed with restart), `2` = B2 (B1
+ binary attachments), `H` = hierarchical addressing, `M` =
MD-style routing.  A trailing `$` marks the end.

LinBPQ's SID adapts to the local partner-config flags
(`AllowCompressed`, `UseB1Protocol`, `UseB2Protocol`,
`AllowBlocked`) — the rule is in
[`BBSUtilities.c::9092`][sid-rule].

[sid-rule]: https://github.com/M0LTE/linbpq/blob/master/BBSUtilities.c

## Proposal commands

Sender proposes a message; receiver replies with an acceptance
code.

```
FB P MID FROM TO @ROUTE SIZE
FA P Title FROM TO @ROUTE
FC P MID FROM TO @ROUTE SIZE [BIDSIZE]
```

| Command | Used for |
|---|---|
| `FA` | Text-mode (B0) — full title and body inline. |
| `FB` | B1 binary — header here, compressed body follows. |
| `FC` | B2 binary — header here, compressed body with attachments follows. |
| `FF` | "Nothing to forward" — terminates an empty session. |
| `FQ` | Terminate session normally. |
| `F>` | Checksum after an FB/FC block — sender includes a one-byte SUM, receiver verifies. |
| `FS` | Receiver's response after a batch of proposals. |

Multi-proposal batches are common — sender sends 1–5 `FB`/`FC`
lines back-to-back, then receiver answers with a single `FS`
line whose payload is one acceptance code per proposal:

```
sender   : FB P MID1 ...
sender   : FB P MID2 ...
sender   : FB P MID3 ...
receiver : FS YYY
```

Acceptance codes:

| Code | Meaning |
|---|---|
| `Y` | Accept the proposal — send the body. |
| `N` | Reject — sender skips this one. |
| `=` | "I already have this BID, don't bother." |
| `+` | Resume from a previous interrupted transfer. |

## B1 / B2 binary framing

After a `Y` acceptance, the body comes over the wire framed by
ASCII control bytes:

```
SOH   (0x01)  +  filename byte-len  +  filename  +  data...
STX   (0x02)  +  body byte-len      +  body...
EOT   (0x04)
```

`SOH` headers introduce a "file" — the message itself is one,
attachments (B2 only) are additional ones.  `STX` carries each
chunk of compressed body data.  `EOT` ends the transfer.

Followed by `F>` and a one-byte checksum, which is the sum of
every body byte mod 256.  The receiver verifies and either
proceeds to the next proposal or aborts.

Compression is LZ-style with restart support in B1; B2 keeps the
same compression but allows multiple `SOH`-headed entries in one
transfer (so attachments can ride along).

## Time-out and recovery

If either side stops responding mid-transfer, the L2 layer
eventually disconnects and the `FwdInterval` schedule retries
the dial.  B1 and B2 transfers are restartable — the `+`
acceptance code on the next attempt picks up from where the
previous failed.

## Modes summary

| Mode | Compressed | Restart | Attachments | Modern partner sends |
|---|---|---|---|---|
| MBL/RLI plain text | no | no | no | rarely |
| B0 text | no | no | no | almost never |
| B1 (FB) | yes | yes | no | common between BPQ systems |
| B2 (FC) | yes | yes | yes | preferred between BPQMail / Winlink |

LinBPQ will always offer the highest mode the partner SID
declares, falling back as needed.

## Spec violations LinBPQ tolerates

LinBPQ is conservative about partner spec compliance — it
accepts a few edge cases that strict readings of the FBB doc
would reject:

- Oversized `From:` / `To:` fields (truncates to the spec limit).
- Non-`F`-prefix commands during the proposal phase (logs and
  ignores).
- Missing `F>` checksum on a body (accepts, doesn't ack).

These exist because the wild has lots of slightly-broken
implementations.  Don't rely on them when writing a new BBS;
implement to spec.
