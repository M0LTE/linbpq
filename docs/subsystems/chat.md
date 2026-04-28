# Chat node

BPQChat is a real-time, IRC-shaped chat server with multi-room
support and inter-node link propagation.  The code lives in
`bpqchat.c` and is linked into `linbpq` — pass `chat` on the
command line (or set `LINCHAT` in `bpq32.cfg`) to start it
alongside the node.

!!! note "Upstream and source"
    Re-presentation of John Wiseman's [Hints and Kinks][hk]
    chat-network section and the [BPQ Chat Map][chatmap] page,
    cross-checked against `bpqchat.c`.

[hk]: https://www.cantab.net/users/john.wiseman/Documents/HintsandKinks.html
[chatmap]: https://www.cantab.net/users/john.wiseman/Documents/BPQChatMap.htm

## Enabling

```bash
./linbpq chat
```

…or in `bpq32.cfg`:

```ini
LINCHAT
```

Plus an `APPLICATION` line so users can type `CHAT` at the node
prompt and (optionally) so other nodes can connect to a
`CHAT`-advertising callsign:

```ini
APPLICATION 2,CHAT,,N0CALL-2,BPQCHT,255
```

| Field | Meaning |
|---|---|
| `2` | Application slot (must match `ApplNum` in `chatconfig.cfg`). |
| `CHAT` | Command word at the node prompt. |
| `N0CALL-2` | Direct-connect callsign. |
| `BPQCHT` | NODES alias. |
| `255` | Quality. |

## chatconfig.cfg

`chatconfig.cfg` is a libconfig-format file in the working
directory.  First boot writes a default; later edits go through
the chat sysop console or directly in the file.  Top-level group
is `main:`.

| Key | Effect |
|---|---|
| `ApplNum` | Application slot the chat server attaches to (matches the `APPLICATION` line). |
| `MaxStreams` | Concurrent chat sessions. |
| `MapPosition` | Position string for the chat-network map (see below). |
| `MapPopup` | HTML-formatted hover/popup text on the map. |
| `PopupMode` | `0` = hover, `1` = click.  Use `1` if the popup contains a clickable link. |
| `OtherChatNodes` | Comma- or CRLF-separated list of peer chat nodes to link to.  Each entry is a node alias / callsign or a multi-line connect script. |
| `Bells` / `FlashOnBell` / `WarnWrap` / `WrapInput` / `StripLF` | Per-stream display flags inherited from the legacy desktop client. |
| `CloseWindowOnBye` / `FlashOnConnect` | Same.  Largely irrelevant on Linux. |

## Linking nodes

Set `OtherChatNodes` on each side to the alias / call of the
peer.  Two matching configs and a route between them is enough:

```
OtherChatNodes = "N0BBB-2";
```

Connections come up *lazily* — only when a user is actually using
the chat — and shut down a few seconds after the last user
disconnects, so a dormant chat network doesn't waste channel time.

For peers that need a multi-step connect, supply a script with CR
separators rather than commas:

```
OtherChatNodes = "C 2 N0BBB\r\nCHAT";
```

Each `\r\n`-separated line is fed to the link in turn before the
chat-server SID exchange begins.

### Mutual definitions are required

If you list a peer that doesn't list you back, the link will
flap — every user join / leave on your side triggers the peer to
reject and immediately retry.  Both ends must define each other.

### Topology recommendations

- 2–3 peers per node is plenty.
- Avoid mesh loops; the chat server doesn't suppress duplicates
  the way NET/ROM does.
- Use AX/IP-UDP for inter-node links wherever possible — the
  chat protocol is sensitive to round-trip jitter and drop, and
  packet over the air doesn't help.

## Sysop status

The chat server treats locally-attached sessions as sysop —
that means the system console, BPQTerminal directly attached,
and *anything coming in via the Telnet driver*.  An incoming
session over an AX.25 port is not sysop, regardless of the user.

The user record password (declared in the Telnet `USER=` line)
is therefore the only thing protecting sysop status from a
remote login.  Pick something strong.

## User commands

All chat commands start with `/`:

| Command | Effect |
|---|---|
| `/H` | Help — lists every command. |
| `/N <name>` | Set your displayed name (used when you join a topic). |
| `/U` | List users currently online (across linked nodes). |
| `/T` | List topics. |
| `/T <name>` | Create or join topic `<name>`.  All your text goes there until you `/T` again. |
| `/J <topic>` | Same as `/T <topic>`. |
| `/L` | Leave the current topic. |
| `/P` | List linked peer nodes. |
| `/M <user> <text>` | Private message a user. |
| `/B` | Bye — leave the chat server. |
| `/W` | Who am I — print your name and current topic. |

Lines that don't start with `/` go to the current topic, broadcast
to every user joined to that topic on every linked node.

## Chat network map

The map at `http://guardian.no-ip.org:81/ChatNetwork.htm` shows
every chat-server node that has reported a position.  Reporting
is via small UDP datagrams sent on link state changes and every
10 minutes thereafter.

Set `MapPosition` to one of these formats:

- Decimal: `56.41805 -5.4966` (negative south / west)
- APRS: `5828.541N 00612.684W`
- DMS: `56°25'5" N 5°29'48" W`

`MapPopup` is HTML — links, line breaks, formatting all work.
Set `PopupMode = 1` if the popup contains a `<a href>` you want
clickable.

The reporting protocol is best-effort UDP — packets can drop —
but the server fills in only fields it received non-empty, so a
dropped update doesn't blank you off the map.

