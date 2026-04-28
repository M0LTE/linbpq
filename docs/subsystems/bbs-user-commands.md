# BBS user commands

Reference for what users type at the BBS prompt — separate from
the [node-prompt commands][node].  A BBS session begins after
`BBS` is typed at the node prompt, or when an inbound L2 connect
hits the BBS callsign or alias.

[node]: ../node-commands.md

!!! note "Upstream and source"
    Re-presentation of John Wiseman's [BBS User Commands][upstream]
    page.  Behaviour cross-checked against `MailCommands.c` and
    the BBS-driven integration tests under `tests/integration/`.

[upstream]: https://www.cantab.net/users/john.wiseman/Documents/BBSUserCommands.html

## Conventions

- Commands are case-insensitive.
- A single-letter or short prefix is usually enough — for example
  `R` for `READ`, `LL 5` for `LIST LAST 5`.
- Some commands accept a callsign (`call`) or hierarchical address
  (`call@bbs.area.country.continent`).
- A trailing `?` on the partial command lists matching commands.

## Help and navigation

| Command | Effect |
|---|---|
| `?` / `HELP` | List every available command. |
| `HELP <cmd>` | Detailed help for a specific command. |
| `BYE` / `B` | Disconnect.  At the node prompt this is `BYE` too. |
| `NODE` | Leave the BBS, return to the node prompt. |
| `A` | Abort the current paged listing. |
| `OP <n>` | Set output paging — `0` disables, otherwise pause every `n` lines. |
| `V` / `VERSION` | Print BPQMail version. |
| `X` | Toggle expert (short-prompt) mode. |

## Profile

| Command | Effect |
|---|---|
| `N <name>` | Set or change your name (≤ 12 chars). |
| `Q <qth>` | Set your QTH / location. |
| `Z <zip>` | Set your ZIP / postcode. |
| `HOME <bbs>` | Set your home BBS — where personal mail forwards to.  Use a `.` to clear. |

## Listing messages

| Command | Effect |
|---|---|
| `L` | New messages since you last looked. |
| `L <a>-<b>` | Messages numbered `<a>` to `<b>` inclusive. |
| `L <n>-` | All messages from `<n>` onward. |
| `LL <n>` | The last `<n>` messages. |
| `LR` | Messages, newest first. |
| `LM` | Messages addressed to you. |
| `LB` | Bulletins. |
| `LC` | Bulletin categories (TO-fields in use). |
| `LT` | NTS traffic. |
| `LN` | Same as `L` filter `N` — messages with status `N`. |
| `L<x>` | Filter by status: `D`/`F`/`H`/`K`/`N`/`Y`/`$` (sysop only for `H`/`K`). |
| `L< <call>` | Messages **from** `<call>`. |
| `L> <call>` | Messages **to** `<call>`. |
| `L@ <bbs>` | Messages routed via `<bbs>`. |

## Reading messages

| Command | Effect |
|---|---|
| `R <n>` | Read message `<n>`. |
| `R <a> <b> <c>` | Read several messages. |
| `RM` | Read every new message addressed to you in turn. |
| `READ <name>` | Download a file from the public files area. |
| `YAPP <name>` | YAPP-protocol binary download (terminal must support YAPP). |

## Sending messages

| Command | Effect |
|---|---|
| `SP <call>` | Send a personal message to `<call>`. |
| `SP <call>@<bbs>` | Personal mail routed via `<bbs>`. |
| `SB <to>@<area>` | Send a bulletin (e.g. `SB ALL@GBR`). |
| `ST <call>` | Send NTS traffic. |
| `S <call>` | Same as `SP <call>` — defaults to personal. |
| `SR <n>` | Reply to message `<n>`. |
| `SC <n> <call>@<bbs>` | Forward (copy) a message you've read to another address. |

After the address, the BBS prompts for `Title:` then accepts the
body until you end with `/EX` on a line by itself or `Ctrl/Z`.

## Deleting messages

| Command | Effect |
|---|---|
| `K <n>` | Kill (queue for deletion) message `<n>`.  Only your own messages, unless sysop. |
| `KM` | Kill every unread message addressed to you. |

## Directory and white pages

| Command | Effect |
|---|---|
| `I` | Print the BBS info text (set by sysop in `linmail.cfg`). |
| `I <call>` | White-pages lookup; wildcards allowed. |
| `I@ <bbs>` | List users whose home BBS is `<bbs>`. |
| `IH <route>` | List users in a hierarchical-route area. |
| `IZ <zip>` | List users by ZIP. |

## Winlink integration

| Command | Effect |
|---|---|
| `CMSPASS <password>` | Store your Winlink Secure-Logon password in the BBS user record. |
| `POLLRMS Enable` / `Disable` | Turn RMS polling on / off for your account. |
| `POLLRMS <ssid>...` | Configure which SSIDs of your call to fetch on each RMS poll (`0` for the bare call). |

## Sysop-only commands

| Command | Effect |
|---|---|
| `AUTH` | One-time-password sysop unlock from a remote session.  Pair with the upstream BPQAUTH passcode generator. |
| `LH` | List held messages. |
| `LK` | List killed (deletion-queued) messages. |
| `UH ALL` / `UH <n>...` | Release held messages back to the active queue. |
| `KH` | Permanently delete every held message. |
| `K< <call>` / `K> <call>` | Kill all messages from / to a callsign. |
| `EXPORT` | Export message text to a file (run with no arg for usage). |
| `IMPORT` | Re-import previously exported messages. |
| `EU [<call>]` / `EDITUSER <call>` | Edit a user record from the BBS prompt. |
| `FWD ...` | Manage forwarding partners (`FWD HELP`). |
| `REROUTEMSGS` | Re-evaluate routing on every queued message. |
| `SETNEXTMESSAGENUMBER <n>` | Force the running message number counter. |
| `DOHOUSEKEEPING` | Run the daily maintenance pass on demand. |
| `SHOWRMSPOLL` | Show the current RMS polling configuration. |
