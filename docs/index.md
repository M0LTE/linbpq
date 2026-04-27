# LinBPQ documentation

!!! warning "AI-generated, in progress"
    This site is being built up from John Wiseman G8BPQ's
    upstream HTML documentation, reorganised around user journeys
    and fact-checked against the binary plus the integration test
    suite.  Expect rough edges and gaps until the rewrite project
    completes — see the [plan][docsplan] for status.

LinBPQ is a Linux/macOS port of John Wiseman's
[BPQ32][bpq32upstream] amateur-radio packet switch.  It runs as a
single long-lived daemon (`linbpq`) built from ~150 C source
files, configured by a single `bpq32.cfg`.  In one binary it
provides:

- An AX.25 / NET/ROM packet switch
- A BBS (BPQMail) with FBB inter-BBS forwarding
- A real-time chat node
- An APRS gateway with iGate uplink

It speaks to radios over a long list of modems (KISS, Pactor
families, ARDOP, VARA, FLDigi, MULTIPSK, WinRPR, HSMODEM) and to
clients over Telnet, AGW, KISS-over-TCP, AX.25-over-UDP, NET/ROM-
over-TCP, MQTT, and a JSON / SNMP / Winlink CMS family.

## Where to start

<div class="grid cards" markdown>

- :material-rocket-launch: __[Getting started][getting-started]__

    Stand a node up from a clean Linux box: build, minimal
    `bpq32.cfg`, first telnet login, smoke-test the wire.

- :material-cog: __[Configuration reference][config-ref]__

    Every cfg keyword the parser accepts, what subsystem owns it,
    cross-referenced to the source line that consumes it.

- :material-application-cog: __[Subsystems][subsystems]__

    BBS / mail, chat, APRS — what each does, how to enable it,
    the relationship between cfg keywords and runtime commands.

- :material-network: __[Protocols and interfaces][protocols]__

    AX.25, NET/ROM, AX/IP-over-UDP, KISS, FBB forwarding,
    Winlink CMS — the wire formats LinBPQ implements.

- :material-console: __[Node prompt commands][node-commands]__

    Reference for every command on the telnet node prompt.
    Generated from `Cmd.c::COMMANDS[]`, fact-checked against
    the integration suite.

- :material-source-pull: __[Upstream documentation][upstream]__

    John Wiseman's original HTML docs, with a per-page status
    of "rewritten / partial / pending" against this site.

</div>

## Why a re-presentation

[John Wiseman's docs][bpqdocs] are the authoritative source on
LinBPQ's behaviour and have been kept up to date for two decades.
What this site adds is *organisation by audience and task*: the
upstream docs are arranged loosely as files-as-found, while this
site groups material by what someone actually wants to do, with
deep links into the source and tests.

This is a re-presentation, not a fork.  The technical content is
faithful to the upstream and we cite John's pages prominently.
Where this site disagrees with the upstream, that's a bug in this
site or a behaviour change in the binary that needs an issue
filed — please open a [GitHub issue][issues].

[bpq32upstream]: https://www.cantab.net/users/john.wiseman/Documents/BPQ32%20Documents.htm
[bpqdocs]: https://www.cantab.net/users/john.wiseman/Documents/
[getting-started]: getting-started/index.md
[config-ref]: configuration/reference.md
[subsystems]: subsystems/index.md
[protocols]: protocols/index.md
[node-commands]: node-commands.md
[upstream]: project/upstream.md
[docsplan]: plan.md
[issues]: https://github.com/M0LTE/linbpq/issues
