# BBS / mail (BPQMail)

BPQMail is the BBS application that ships in-process inside
`linbpq`.  It handles personal mail and bulletins, forwards to
peer BBSes over FBB, and bridges to Winlink and Internet email.

This page covers what the BBS does and how to configure it.
Sub-pages:

- [BBS user commands](bbs-user-commands.md) — what users type
  at the BBS prompt.
- [Inter-BBS forwarding](bbs-forwarding.md) — partner setup,
  HRoutes, time-bands, FBB protocol.
- [Email gateways](bbs-email.md) — POP3 / SMTP / NNTP /
  Winlink / ISP gateway.

!!! note "Upstream and source"
    Re-presentation of John Wiseman's
    [BPQ Mail Server][upstream] and
    [BPQ Mail Server Configuration][upstream-cfg], plus the
    [Hints and Kinks][hk] page.  Cross-checked against
    `bpqmail.h`, `BBSUtilities.c`, and `MailCommands.c`.

[upstream]: https://www.cantab.net/users/john.wiseman/Documents/MailServer.html
[upstream-cfg]: https://www.cantab.net/users/john.wiseman/Documents/MailServerConfiguration.html
[hk]: https://www.cantab.net/users/john.wiseman/Documents/HintsandKinks.html

## What the BBS does

- Personal mail (`P`-type), bulletins (`B`-type), traffic (`T`-type)
- FBB compressed forwarding (B / B1 / B2) over AX.25, NET/ROM,
  AX/IP-UDP and TCP
- MBL/RLI plain-text forwarding for legacy partners
- White-pages directory of users and home BBSes
- POP3 / SMTP / NNTP servers for desktop email + news clients
- Winlink CMS gateway (RMS) for `@winlink.org` traffic
- Optional ISP gateway for amateur ↔ Internet email

## Enabling the BBS

Either pass `mail` on the command line:

```bash
./linbpq mail
```

…or set `LINMAIL` in `bpq32.cfg`:

```ini
LINMAIL
```

Both forms are equivalent — pick whichever fits your launcher.

You also need an `APPLICATION` line so the BBS shows up at the
node prompt and (optionally) advertises a callsign on the
network:

```ini
APPLICATION 1,BBS,,N0CALL-1,BPQBBS,200
```

| Field | Meaning |
|---|---|
| `1` | Application slot.  The BBS expects to be slot 1 by default; if you put it somewhere else, set `BBSApplNum` in `linmail.cfg` to match. |
| `BBS` | What users type at the node prompt to enter the BBS. |
| `N0CALL-1` | Callsign at which other stations and BBSes can connect to the BBS directly. |
| `BPQBBS` | Alias the BBS advertises in NODES broadcasts. |
| `200` | Quality.  Set ≥ `MINQUAL` for the BBS to propagate. |

## linmail.cfg

`linmail.cfg` is a [libconfig][libconfig]-format file.  It's
created on first run if it doesn't exist; subsequent edits can
go through the web admin or directly in the file.  Three top-level
groups: `main`, `BBSForwarding`, `BBSUsers`, plus an optional
`Housekeeping`.

[libconfig]: http://hyperrealm.github.io/libconfig/

### main

Mandatory parameters:

| Field | Meaning |
|---|---|
| `BBSName` | The BBS callsign (typically the node call, sometimes with `-1`). |
| `SYSOPCall` | Sysop login.  Defaults to `BBSName` if blank. |
| `H-Route` | Your hierarchical routing — typically `BBSCALL.AREA.COUNTRY.CONTINENT` (e.g. `G8BPQ.#23.GBR.EU`).  Used to decide whether to accept inbound bulletins. |
| `BBSApplNum` | Application slot the BBS should attach to (typically `1`). |
| `Streams` | Maximum concurrent BBS sessions. |

Behavioural toggles:

| Field | Effect |
|---|---|
| `EnableUI` | If `1`, the BBS broadcasts FBB-compatible "mail-for" UI frames listing held messages.  Pair with `Send Mail For Beacons`. |
| `RefuseBulls` | If `1`, refuse incoming bulletins (personal mail still accepted). |
| `SendBBStoSYSOPCall` | If `1`, mail addressed to the BBS callsign forwards on to `SYSOPCall`. |
| `DontHoldNewUsers` | If `0`, messages from first-time users land in the held queue for sysop review. |
| `DontCheckFromCall` | If `1`, accept messages whose `From` field doesn't match the connected user. |
| `DontNeedHomeBBS` | If `0`, refuse messages from users whose home-BBS field is empty. |
| `DontNeedName` | If `0`, prompt for and require a real name on first login. |
| `AllowAnon` | If `1`, allow `Anonymous` as a sender. |
| `MaxTXSize` | Refuse messages larger than this when sending. |
| `MaxRXSize` | Refuse messages larger than this when receiving. |
| `MailForInterval` | Minutes between "Mail for…" UI broadcasts.  `0` disables. |
| `Log_BBS`, `Log_TCP` | Per-channel logging toggles. |

Network ports (in main):

| Field | Effect |
|---|---|
| `POP3Port` | TCP port for the POP3 server (typically 110, or 8110+ for unprivileged). `0` disables. |
| `SMTPPort` | TCP port for the SMTP server (typically 25, or 8025+ for unprivileged). `0` disables. |
| `NNTPPort` | TCP port for NNTP (typically 119). `0` disables. |
| `Enable Remote Access` | If `0`, only loopback clients can use POP3/SMTP/NNTP. |

### BBSUsers

User records, one per call:

```
BBSUsers:
{
  G8BPQ = "John^^^^^^0^16^0^^^0^0";
};
```

The string is `^`-delimited and stored verbatim.  Position-by-position:

| # | Field |
|---|---|
| 0 | Name |
| 1 | Address (free-form) |
| 2 | HomeBBS |
| 3 | QRA / locator |
| 4 | BBS password |
| 5 | ZIP |
| 6 | CMSPass (Winlink CMS password) |
| 7 | Last message number read |
| 8 | Flags (bitfield — see below) |
| 9 | PageLen (output paging) |
| 10 | BBSNumber (partner-BBS records only) |
| 11 | Reserved |
| 12 | Reserved |

User flag bits (from `bpqmail.h`):

| Hex | Name | Meaning |
|---|---|---|
| `0x01` | `F_SYSOP` | Sysop privileges. |
| `0x02` | `F_PMS` | Personal Message Server — allows FBB-compressed forwarding from clients like Winpack. |
| `0x04` | `F_EXPERT` | Short-form prompt. |
| `0x08` | `F_EXCLUDED` | Block this user. |
| `0x10` | `F_BBS` | Forwarding-partner BBS, not a human. |
| `0x20` | `F_HOLD` | Hold all this user's messages pending sysop release. |
| `0x40` | `F_NTSMPS` | NTS message-pickup station. |
| `0x80` | `F_RMS` | Auto-redirect to `<call>@winlink.org`. |
| `0x100` | `F_APRS` | "Send Mail For" notification via APRS. |
| `0x1000` | `F_EMAIL` | ISP-gateway access. |
| `0x2000` | `F_HOLDMAIL` | Hold-pending alternative. |

(Other bits exist for RMS-Express recognition, secure-CMS, etc;
add through the web UI rather than hand-rolling the bitmask.)

### BBSForwarding

Per-partner forwarding configuration.  See the
[Inter-BBS forwarding][fwd] page for full details.

[fwd]: bbs-forwarding.md

## Web admin

`HTTPPORT` in the Telnet driver block (typically 8080) serves a
web UI under `/Mail/` for everything BBS-related: configuration
tabs, user records, forwarding partners, message browsing,
white-pages, log viewing.

Local connections (`127.0.0.1`) bypass authentication; remote
connections need a Telnet `USER=` record with sysop rights and
the corresponding password.

## Message status codes

The BBS marks each message with a single-character status
visible in `L`, `LL`, etc:

| Code | Meaning |
|---|---|
| `N` | New, unread by anyone. |
| `Y` | Read at least once. |
| `$` | Bulletin with pending forwarding. |
| `F` | Forwarded to all eligible partners. |
| `K` | Killed (in deletion queue). |
| `H` | Held — invisible to users, awaiting sysop action. |
| `D` | Delivered (NTS message). |

## Housekeeping

A maintenance pass runs once a day at the configured
`Maintenance Time`:

1. Permanently delete `K`-flagged messages.
2. Expire BIDs older than `BID Lifetime` (so duplicate detection
   doesn't grow unbounded).
3. Expire messages older than the per-type lifetime; messages
   received with a date older than this are auto-held.
4. Trim log files older than `Log File Lifetime`.

`DOHOUSEKEEPING` runs the pass on demand from the BBS sysop
prompt.

| Field | Effect |
|---|---|
| `Maintenance Time` | Local clock time (HHMM) for the daily run. |
| `Max Message Number` | When the running message-number counter exceeds this, renumber outstanding messages from 1.  Set high (e.g. 999999) to avoid renumbering churn. |
| `BID Lifetime` | Days to retain BID for duplicate detection. |
| `Log File Lifetime` | Days to keep `Log/*` files before deleting. |
| `Delete Log And Message Files to Recycle Bin` | Windows-only — soft-delete via the OS recycle bin. |
| `Send Non-delivery Notifications` | Generate NDR mail for undeliverable P/T messages. |
| `Suppress Mailing of Housekeeping Results` | Skip the daily housekeeping summary mail to sysop. |
| `Save Registry` | Windows-only — checkpoint config to the registry. |

## Hints and gotchas

- **Sysop status is local-only by default.**  Console and local
  programs (BPQTerminal) get sysop automatically; remote
  connections come in as ordinary users.  *Telnet logins are
  treated as local* — this means the password for any sysop-
  flagged Telnet `USER=` record is the only barrier to remote
  sysop access.  Pick a strong one.[^sysop]

- **FBB forwarding wants a separate TCP port.**  FBB uses raw
  TCP, not telnet line discipline.  If you want to forward over
  TCP/IP rather than over the air, configure `FBBPORT=` alongside
  `TCPPORT=` in the Telnet driver block — different port numbers,
  same login family.

- **Topology: keep partner counts low.**  Two or three direct
  partners is plenty.  HRoutes plus the implicit AT route to each
  partner do the heavy lifting; flooding bulletins to many partners
  multiplies traffic without adding coverage.

- **Mutual partner records.**  A BBS that connects to you and
  isn't in your `BBSForwarding` list will be treated as a regular
  user and refused B/B1/B2 SID exchange.  Add a partner record
  even if you never connect outbound — set `Enabled = 0` and the
  BBS won't dial out, but inbound exchanges still work.

[^sysop]: From `BBSUtilities.c` — Telnet sessions are tagged as
    LocalUserSession and bypass the call-and-passcode challenge.
