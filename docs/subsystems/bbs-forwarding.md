# Inter-BBS forwarding

BPQMail forwards mail to peer BBSes using FBB compressed
forwarding (B / B1 / B2) over any L2 transport — AX.25, NET/ROM,
AX/IP-UDP, telnet/TCP — plus a legacy MBL/RLI plain-text mode
for old systems.  This page covers how to configure a
forwarding partner.

The wire-protocol details (SID exchange, FA/FC proposal flow,
B2 binary blocks) are in the [FBB protocol page][fbb].

[fbb]: ../protocols/fbb-forwarding.md

!!! note "Upstream and source"
    Re-presentation of John Wiseman's
    [Mail Forwarding][upstream] and
    [Winlink Forwarding][rmsupstream] pages.  Cross-checked
    against `BBSUtilities.c::CheckABBS`, `FBBRoutines.c`, and
    `MailRouting.c`.

[upstream]: https://www.cantab.net/users/john.wiseman/Documents/Forwarding.html
[rmsupstream]: https://www.cantab.net/users/john.wiseman/Documents/RMSForwarding.html

## A partner record at a glance

```
BBSForwarding:
{
  N0BBB:
  {
    BBSHA          = "N0BBB.#NCA.CA.USA.NA";
    HRoutesP       = "USA.NA, CA.USA.NA";    /* personals */
    HRoutes        = "WW";                   /* bulletins */
    TOCalls        = "";
    ATCalls        = "LOCAL";
    FWDTimes       = "0000-2359";
    ConnectScript  = "C 2 N0BBB", "BBS";
    Enabled        = 1;
    RequestReverse = 0;
    AllowBlocked   = 1;
    AllowCompressed= 1;
    UseB1Protocol  = 1;
    UseB2Protocol  = 1;
    SendCTRLZ      = 0;
    FWDPersonalsOnly = 0;
    FWDNewImmediately = 1;
    FwdInterval    = 30;       /* minutes */
    RevFWDInterval = 0;
    MaxFBBBlock    = 1024;
    ConTimeout     = 300;
  };
};
```

There must be a matching record in `BBSUsers` carrying the
`F_BBS = 0x10` flag and a positive `BBSNumber`, otherwise BPQMail
treats the partner as a regular user and refuses FBB SID exchange.

## Routing logic

When BPQMail decides where a message goes, it consults each
partner record and picks the one with the most-specific match.
*Personals* and *bulletins* use different match fields:

- **Personals** match against `HRoutesP` (personal HRoutes), or
  fall back to the implicit AT route to `BBSHA`.  The partner whose
  HRoutes share the most trailing elements with the addressee's
  HR string wins.
- **Bulletins** match against `HRoutes` (bulletin HRoutes), plus
  `TOCalls` and `ATCalls` for direct-match overrides.

### Example: personal mail

Two partners:

| Partner | `BBSHA` |
|---|---|
| `N0AAA` | `N0AAA.#NCA.CA.USA.NA` |
| `N0BBB` | `N0BBB.GBR.EU` |

A message addressed to `XXXXX@WHOEVER.#23.GBR.EU` matches
`N0BBB`'s `BBSHA` with two trailing elements (`GBR.EU`) and
`N0AAA`'s with zero.  BPQMail picks `N0BBB`.

A message addressed to `XXXXX@WHOEVER.#NCA.CA.USA.NA` flips the
choice the other way.

### Example: bulletins

A bulletin to `B @ ALL.EU`:

- Partner whose `HRoutes` includes `EU` or any superset is eligible.
- Direct `TOCalls` / `ATCalls` matches override the HR-based routing.
- Bulletins fan out to *every* eligible partner, not just the best
  match — so `HRoutes = "WW"` on both sides means everyone gets
  every bulletin you accept.

!!! warning "Known bug — HRoutes-based bulletin routing"
    [Issue #7][issue7] tracks `MatchMessageto​BBSList` returning 0
    for `B @ ALL.EU` against `HRoutes = ".EU"` when the matcher in
    `CheckABBS` lines 3629-3650 should fire.  Workaround: list
    each `<area>.EU` you want to receive.

[issue7]: https://github.com/M0LTE/linbpq/issues/7

## Connect scripts

`ConnectScript` is a list of strings.  Each line is sent in turn
to the underlying connection.  The script ends when:

- The remote end answers with the FBB SID exchange (BPQMail
  detects `[<sid>]` and starts forwarding), **or**
- the script's last line has been sent (BPQMail then waits for the
  partner's SID).

### Simple script — local NET/ROM

```
"C N0BBB"
```

Connect to N0BBB via the closest route in NODES.

### Script with port

```
"C 2 N0BBB"
"BBS"
```

Connect on port 2 (e.g. an AX/IP-UDP partner port), then enter
the BBS application on the remote side before SID exchange begins.

### Script across multiple nodes

```
"C HUB1"
"C HUB2"
"C 3 N0BBB"
```

Hop via two intermediate nodes.

### HF link with line tuning

```
"PACLEN 80"
"PASSWORD"
"MAXFRAME 4 1"
"RETRIES 4 10"
"FRACK 4 30"
"C 4 N0BBB"
```

`PACLEN` / `MAXFRAME` / `RETRIES` / `FRACK` are interpreted as
ordinary sysop node-prompt commands; the script needs `PASSWORD`
to lift sysop restrictions.

### Time-of-day script switching (`TIMES`)

```
"TIMES 0000-1159"
"C N0BBB"
"TIMES 1200-2359"
"PAC 80"
"ATTACH 4"
"C N0BBB"
```

Different hours pick different scripts.  Time-bands cannot cross
midnight; split with two adjacent bands.

### Fallback (`ELSE`)

```
"C N0BBB-10"
"ELSE"
"C N0CCC-10"
"ELSE"
"C N0DDD-10"
```

If a script step fails the next `ELSE` block runs.

### Other directives

| Directive | Effect |
|---|---|
| `RMS` | Connect to a Winlink CMS server (Telnet driver with `CMS=1`). |
| `PAUSE <s>` | Wait `<s>` seconds — useful after a `RADIO` frequency change. |
| `RADIO <freq> <mode> <port>` | Couple to a `RIGCONTROL` block to retune the radio. |
| `RADIO AUTH` | Generate a one-time password for remote rig control. |
| `INTERLOCK <port>` | Lock other ports out for the duration of the script (paired Pactor / WINMOR setups). |
| `SKIPPROMPT` | Don't treat a `>` prompt as the end of node-traversal. |
| `TEXTFORWARDING` | MBL/RLI plain-text forwarding for legacy partners (no SID exchange; terminate with `Ctrl/Z`). |
| `FILE` | Export-to-file destination (for non-network forwarding). |

## MSGTYPES

`MSGTYPES` (set on the partner record, separate from the
ConnectScript) controls what kinds of message and what size
limits apply on each direction:

| Form | Meaning |
|---|---|
| `MSGTYPES PT` | Send personal + traffic only.  No reverse forwarding accepted. |
| `MSGTYPES BR` | Send bulletins of any size.  Accept reverse forwarding. |
| `MSGTYPES PTRB1000` | All types, bulls capped at 1000 bytes, accept reverse. |
| `MSGTYPES P1000T1000B1000R` | All types with per-type byte caps, accept reverse. |

The `R` flag is what enables the partner to push messages *to*
you on the same connection.  Between two BPQMail systems, including
`R` propagates the local MSGTYPES restrictions to the partner.

## Time bands

`FWDTimes` controls when BPQMail will dial out to a partner:

```
FWDTimes = "0800-1200", "1400-1600";
```

Multiple ranges allowed.  All times are UTC.  Bands cannot
straddle midnight — split:

```
FWDTimes = "1800-2359", "0000-0800";
```

Tight windows work:

```
FWDTimes = "0800-0810", "0900-0910";
```

…but make sure `FwdInterval` is shorter than the window or
you'll miss the slot.

## Auto-connect cadence

| Field | Effect |
|---|---|
| `Enabled = 1` | Permits this partner record at all.  `0` disables outbound dial-out *only* — inbound still works. |
| `FwdInterval = <minutes>` | How often to dial out when there's outbound traffic queued. |
| `RevFWDInterval = <minutes>` | Force a connect even with no outbound queue, to drag in inbound mail.  Usually unnecessary if both ends auto-connect. |
| `RequestReverse = 1` | After SID exchange, ask the partner to dump anything queued for us. |

## FBB protocol toggles

| Field | Effect |
|---|---|
| `AllowCompressed` | Permit B / B1 / B2 compressed forwarding at all.  `0` falls back to MBL/RLI text. |
| `UseB1Protocol` | Allow B1 compressed forwarding (with restart support — recommended where partner supports it). |
| `UseB2Protocol` | Allow B2 binary forwarding (better compression, attachments preserved between BPQ systems). |
| `AllowBlocked` | Send the `F` flag in our SID — tells the partner we accept blocked-FA proposals. |
| `MaxFBBBlock` | Maximum block size in B2 binary mode. |
| `SendCTRLZ` | Use Ctrl/Z (rather than `/EX`) to terminate text-mode messages.  Some partners need this. |

When BPQMail dials out, the SID it sends is computed from the
combination of `AllowCompressed`, `UseB1Protocol`, `UseB2Protocol`
and `AllowBlocked` — see `BBSUtilities.c:9092` for the exact rule
(B2 implies-B1 suppression matters for some old partners).

## Forwarding to / from Winlink (CMS)

The Winlink CMS gateway looks like just another forwarding
partner from the BBS's point of view.  Set up:

1. **Telnet PORT block with `CMS=1`** — this gives you a PORT
   that knows how to authenticate to a Winlink CMS server.
2. **A user record named `RMS`** in `BBSUsers`, with the
   `F_RMS = 0x80` flag and a CMSPass.  This is the gateway account.
3. **Per-user RMS flags** for any local user who wants Winlink
   pickup: enable Poll RMS in their record and configure SSID
   list with `POLLRMS <ssid>...`.
4. **A connect script** of just:
   ```
   "RMS"
   ```
   (The `RMS` directive is special — Telnet driver hands the link
   to the Winlink-CMS handshake code.)


### Sending to Winlink users

Either form works at the BBS prompt:

```
SP rms:john.wiseman@example.com
SP G8BPQ@winlink.org
```

The BBS rewrites the destination to a CMS-compatible address
internally.

### CMS passwords

Winlink Secure-Logon was made mandatory in October 2015.  Each
local user with RMS access needs a `CMSPass` set in their user
record (or via `CMSPASS <password>` from the BBS prompt — the
input is hashed before storage).  If *any* user uses secure
logon, the BBS callsign also needs a CMSPass entry — store it
in the BBS's own user record or the special `RMS` record.

### Attachments

B2 forwarding between BPQMail and Winlink (or any B2-capable
partner) preserves attachments.  Other forwarding methods will
silently drop them.[^attachments]

[^attachments]: Per `BBSUtilities.c` — if the proposal goes out as
    `FA` (text) or `FB` (B1) rather than `FC` (B2), the binary
    parts of the message can't ride along.

## Aliases

`Alias List` (in `linmail.cfg`'s `main` section) maps non-
hierarchical bulletin areas to valid hierarchical ones for routing
purposes only — the message text isn't rewritten:

```
Aliases = ( "AMSAT:WW", "ALLUS:USA", "CALIF:CA.USA", "CANADA:CAN" );
```

A bulletin addressed to `B @ AMSAT` then routes as if it were
addressed to `B @ WW`.

