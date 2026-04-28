# Subsystems

LinBPQ is a single binary that hosts a packet switch plus three
optional applications.  Each application runs in-process —
`linbpq` linked against the BBS, chat-server and APRS code —
and is enabled by a positional argument or its equivalent cfg
keyword.

| Subsystem | Enable | Config file | Page |
|---|---|---|---|
| BBS / Mail (BPQMail) | `mail` argv or `LINMAIL` cfg | `linmail.cfg` | [BBS / mail][bbs] |
| Chat node (BPQChat) | `chat` argv or `LINCHAT` cfg | `chatconfig.cfg` | [Chat node][chat] |
| APRS digi/iGate | `APRSDIGI ... ***` block in `bpq32.cfg` | inline | [APRS gateway][aprs] |
| IP gateway | `IPGATEWAY` block in `bpq32.cfg` | inline | [IP gateway][ipgw] |

[bbs]: bbsmail.md
[chat]: chat.md
[aprs]: aprs.md
[ipgw]: ipgateway.md

## How they fit together

Applications attach to *application slots* declared with
`APPLICATION n,…` lines in `bpq32.cfg`.  A slot exposes:

- A user-facing command word at the node prompt (`BBS`, `CHAT`).
- An optional callsign + alias that appears in NODES so other
  nodes can connect directly to the application.
- A connection target (in-process for BBS / chat; a node command
  like `C DXCLUS` for external services).

## Common cfg patterns

### BBS only (telnet-only mailbox)

```ini
SIMPLE=1
NODECALL=N0CALL
NODEALIAS=TEST
LOCATOR=NONE
LINMAIL              ; same as `linbpq mail`

PORT
 ID=Telnet
 DRIVER=Telnet
 CONFIG
 TCPPORT=8010
 HTTPPORT=8080
 MAXSESSIONS=10
 USER=test,test,N0CALL,,SYSOP
ENDPORT

APPLICATION 1,BBS,,N0CALL-1,BPQBBS,200
```

### BBS + Chat

```ini
LINMAIL
LINCHAT

APPLICATION 1,BBS,,N0CALL-1,BPQBBS,200
APPLICATION 2,CHAT,,N0CALL-2,BPQCHT,255
```

### APRS digi alongside the node

```ini
APRSDIGI
 APRSCALL=N0CALL-10
 APRSPath 1=APRS
 ; ... full APRS config ...
***
```

See each subsystem's page for the keyword set inside its block.
