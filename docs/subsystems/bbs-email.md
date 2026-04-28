# BBS email gateways

BPQMail can talk Internet email to:

- **Local desktop clients** — over POP3 (read), SMTP (send) and
  NNTP (newsgroups for bulletins).
- **The wider Internet** — through an SMTP relay you set up with
  your ISP or Gmail, with addresses like
  `<call>@yourdomain.org.uk` or
  `mycall+yourcall@gmail.com`.
- **Winlink** — via the CMS gateway.  See the
  [Forwarding page][fwd] for that side.

[fwd]: bbs-forwarding.md

!!! note "Upstream and source"
    Re-presentation of John Wiseman's
    [eMail Client Configuration][upstream-client] and
    [eMail Gateway][upstream-gw] pages.  Cross-checked against
    `MailTCP.c`, `NNTPRoutines.c` and `BBSUtilities.c`.

[upstream-client]: https://www.cantab.net/users/john.wiseman/Documents/eMailClientConfiguration.html
[upstream-gw]: https://www.cantab.net/users/john.wiseman/Documents/ISPGateway.html

## POP3 / SMTP / NNTP servers

Set the listening ports in `linmail.cfg`'s `main` group:

```
POP3Port = 8110;
SMTPPort = 8025;
NNTPPort = 8119;
```

Standard ports (110 / 25 / 119) need either `setcap
CAP_NET_BIND_SERVICE` on the linbpq binary or an unprivileged
user that's been granted those capabilities.  High-port
alternatives like the ones above don't.

By default the listeners only accept loopback connections — set
`Enable Remote Access = 1` in the same group to open them to
the network.

### Mail-client setup

| Field | Value |
|---|---|
| Username | Your callsign (e.g. `G8BPQ`). |
| Password | The BBS password from your `BBSUsers` record. |
| POP3 host / port | `127.0.0.1` (or your BBS host) / configured POP3 port. |
| SMTP host / port | Same host / configured SMTP port. |
| SMTP authentication | "Outgoing requires authentication", "Use same as incoming". |
| Email address | `yourcall@bbs-call`, or hierarchical (e.g. `g8bpq@g8bpq.gbr.eu`). |

Authentication is mandatory on SMTP — only registered BBS users
can send through your relay.  Without it the BBS becomes an open
relay and you'll find out quickly when the spam catches up.

### NNTP — bulletins as newsgroups

NNTP exposes bulletin areas as a newsgroup tree.  Point your
news client at the `NNTPPort`, log in with your BBS credentials,
and bulletin TO-fields appear as group names (`bull.gbr`,
`bull.eu`, etc).  Posts go back into the bulletin queue and
forward like any other message.

## ISP gateway — sending to Internet email addresses

Two address mappings are needed:

1. **From a local user to the Internet** — local users send to
   `smtp:user@example.com` (the `smtp:` prefix tells the BBS to
   route via the SMTP relay rather than the packet network).
2. **From the Internet back to a local user** — needs a domain
   or Gmail trick (below) so the message routes back to the BBS
   rather than getting stuck in your normal inbox.

Once configured, a sent message includes a `Reply-To:` header
that lets recipients reply naturally — the reply lands at your
relay, which routes it back to the local user.

### Gateway access flag

Gateway access is per-user.  Set `F_EMAIL = 0x1000` on each user
record (in `BBSUsers`) that should be allowed to use the
`smtp:` form.  Without the flag the message is refused.

### Option 1: Your own domain with catch-all forwarding

Easiest if you control a domain:

1. Register `mycall.org.uk`.
2. Configure catch-all forwarding to redirect every address at
   that domain to a single ISP mailbox `bbsmailbox@myisp.com`.
3. Tell BPQMail's SMTP / POP3 client config to log in to that
   ISP mailbox.

Addresses like `g8bpq@mycall.org.uk` arrive at the catch-all,
get pulled into BPQMail by its POP3 client, and route to the
local user `G8BPQ` on the BBS.

### Option 2: Gmail's `+` aliases

Gmail treats anything before a `+` as the same mailbox.  So
`mycall+yourcall@gmail.com` all delivers to `mycall@gmail.com`,
and BPQMail can use the part after the `+` to pick the local user.

Gmail requires SSL and BPQMail's built-in SMTP/POP3 client
doesn't speak SSL natively, so use Stunnel as a local TLS
terminator:

```
[pop3s]
accept = 7301
connect = pop.gmail.com:995

[ssmtp]
accept = 7302
connect = smtp.gmail.com:465
```

Point BPQMail at `127.0.0.1:7301` for POP3 and `127.0.0.1:7302`
for SMTP; Stunnel handles the encrypted hop to Gmail.

### Addressing remote BBS users via email

A standard email address only allows one `@`, so to send through
the gateway to someone on a different BBS you have to encode the
remote-BBS hop:

| Setup | Form |
|---|---|
| Own domain | `<call>!<remotebbs>.<area>.<country>.<continent>@<yourdomain>` |
| Gmail `+` | `<yourgmailuser>+<call>!<remotebbs>.<area>.<country>.<continent>@gmail.com` |

The `!` separates the user from the BBS hierarchy.  BPQMail
rewrites this to a packet-style `<call>@<remotebbs>...` address
internally.

### Reply-To handling

Outgoing Internet email picks up a `Reply-To:` header
automatically — recipients can reply without knowing about
the encoding tricks.  The reply hits your ISP mailbox / Gmail
account, gets pulled into BPQMail, and routes back to the
original local sender.

## Tips

- **Don't run an open relay**: SMTP authentication is the only
  thing standing between you and an abuse complaint.  Don't
  disable it.
- **Whitelist who can use the gateway**: only set `F_EMAIL` on
  users you trust; if that's just you, that's fine.
- **POP3 is destructive**: as is, BPQMail downloads and removes
  messages from the upstream mailbox.  Make sure that's actually
  what you want before you point the BBS at a mailbox you also
  read another way.
- **Local-only by default**: the listeners are loopback-only out
  of the box.  `Enable Remote Access = 1` is a deliberate step.
