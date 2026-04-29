# LinBPQ regression test plan

> Living document. Update as the suite grows or the strategy shifts.

## Coverage gaps from a real-world config

Walked through GB7RDG's production `bpq32.cfg` (Reading, M0LTE)
to spot-check coverage.  What's tested and what's not, captured
here so we can prioritise.

### Currently a canary only — port opens, protocol untouched

- **`FBBPORT`** — *was* canary-only.  Now covered at the **transport
  listener** layer (`test_fbb_host_mode.py`): bare-CR login flow,
  command relay, bad-password loop, initial silence.  The
  **inter-BBS FBB forwarding protocol** (SID exchange, `FB`/`FA`/
  `FC`/`F>`/`FF`/`FQ` proposal rounds, B2 binary blocks per
  [packethacking/ax25spec/doc/fbb-forwarding-protocol.md]) is a
  *separate* layer that runs on top of any transport — covered by
  `test_bbs_forwarding.py` + `helpers/fbb_partner.py` (Python-side
  fake BBS).  *Two real BPQMail daemons* forwarding to each other
  is the next layer; deferred deliberately as lower marginal value
  (Phase 6 footnote).
- ~~**`NETROMPORT`**~~ — covered by `test_netromtcp.py` (FindNeighbour
  gate + ROUTES active-marker behaviour).
- **`APIPORT`** — note: the JSON API itself actually serves on
  `HTTPPORT`; the parallel `APIPORT` listener accepts the connection
  (canary in `test_aux_listeners.py`) but the HTTP-level surface is
  exercised through `HTTPPORT` (`test_api.py`).
- ~~**`SNMPPORT`**~~ — covered by `test_snmp.py` (sysName, sysUpTime,
  unknown-OID drop).

[appsiface]: https://www.cantab.net/users/john.wiseman/Documents/LinBPQ%20Applications%20Interface.html

### Closeout summary

The bulk of this audit's findings now have at least canary-level
coverage; spec-checked tests for the wire-format-y bits.  See the
test docstrings for spec links and per-feature notes.

| Cluster | Coverage | Where |
|---------|----------|-------|
| Identity / map / metrics (MAPCOMMENT, EnableM0LTEMap, ENABLEOARCAPI, EnableEvents, AUTOSAVE) | canary | `test_config_keyword_acceptance.py` |
| `M0LTEMapInfo` per-port | canary | `test_config_to_runtime.py` |
| Compression / globals (L4Compress, L2COMPRESS, T3) | canary | `test_config_keyword_acceptance.py` |
| Beacon / identification (IDMSG:, BTEXT:, CTEXT:) | parse + cross-instance CTEXT | `test_config_keyword_acceptance.py`, `test_two_instance.py`, `test_telnet_driver_options.py` |
| APRS subsystem | core paths | `test_aprs.py` (block parsing, STATUS / SENT / MSGS / BEACON, outbound APRS-IS connect to a fake server) |
| `KISSOPTIONS=ACKMODE` | wire format vs spec | `test_kiss_serial.py` |
| Per-RF-port tuning (RETRIES/MAXFRAME/PERSIST/DIGIFLAG/PACLEN-PPACLEN/TXDELAY/TXTAIL) | round-trips | `test_config_to_runtime.py` |
| Telnet driver options (LOGINPROMPT, PASSWORDPROMPT, block CTEXT, SECURETELNET, DisconnectOnClose, LOCALNET, LOGGING, RELAYAPPL, CMS family) | wire-visible + canaries | `test_telnet_driver_options.py` |
| LinBPQ Apps Interface (`CMDPORT`) | full | `test_cmdport.py` |
| `PASSWORD=` cfg + non-Secure_Session challenge | round-trip | `test_password_challenge.py` |
| LINMAIL, LINCHAT cfg keywords | log lines | `test_config_keyword_acceptance.py` |
| New APPLICATION line format | full | `test_config_to_runtime.py` |
| MQTT publishes + topic doc | full | `test_mqtt.py` + `docs/mqtt-output.md` |
| IPGW `ENABLESNMP` | canary | `test_config_keyword_acceptance.py` |
| BPQAXIP extras (MHEARD ON, BROADCAST, multi-UDP, MAP ... B) | canary + bind | `test_axip_extras.py` |
| FBBPORT transport listener | full | `test_fbb_host_mode.py` |

### Items still deferred from this audit

- ~~**NETROMPORT** beyond canary~~ — done in
  `test_netromtcp.py`.  Drives the NET/ROM-over-TCP framing
  (`Length(2 LE) | Call(10) | PID=0xCF | L3 packet` —
  NETROMTCP.c:27); negative test verifies unknown call closes the
  socket (NETROMTCP.c:500), positive test verifies known call
  flips ``ROUTES`` output to show the active-link `>` marker
  (Cmd.c:1912).
- **APIPORT** beyond canary — already covered separately by
  `test_api.py` (full API surface: info, ports, nodes, links,
  routes, users).  Listener-canary entry in
  `test_aux_listeners.py` is the safety net.
- ~~**SNMPPORT** beyond canary~~ — done in `test_snmp.py`.  Hand-
  built SNMP-v1 GetRequest BER, three OIDs verified: ``sysName.0``
  → ``MYNODECALL``, ``sysUpTime.0`` → non-zero TimeTicks
  (IPCode.c:5365), unknown OID → silent drop.
- **FBB inter-BBS forwarding protocol** — covered by
  `test_bbs_forwarding.py` plus `helpers/fbb_partner.py` (fake-FBB
  partner harness).  "Two real BPQMail daemons forwarding to each
  other" is a *next layer* deferred deliberately (lower marginal
  value than the fake-partner coverage already in place — see Phase 6
  footnote below).
- **Winlink CMS** real protocol — cfg accepted (CMS keyword set
  in the Telnet PORT block) but exercising the CMS handshake needs
  a fake Winlink CMS server.  CMS uses a session-key authentication
  scheme over TCP; building a faithful simulator is significant
  infrastructure (~200-400 LoC + cryptographic specifics).  Open.
- ~~**L4-uplink** ([issue #4](https://github.com/M0LTE/linbpq/issues/4))~~ —
  resolved.  Three cfg knobs (port-block ``QUALITY=``, ``BROADCAST
  NODES``, ``B`` flag on the ``MAP`` line) plus comma-form
  ``ROUTES:`` (keyword=value form misparsed —
  [#12](https://github.com/M0LTE/linbpq/issues/12)) make NET/ROM
  propagation work over AX/IP-UDP.  Locked in by
  `test_two_instance.py::test_nodes_propagation_and_l4_uplink_connect`.
- ~~**Beacon / ID runtime emission**~~ — done in
  `test_long_runtime_beacons.py` (one ~2:15 test exercises both
  ID and BT in a single boot).  Marked `@pytest.mark.long_runtime`;
  `conftest.py`'s `pytest_collection_modifyitems` sorts the
  marker to the front of the xdist queue so it runs in parallel
  with the rest of the suite, not at the end.
- ~~**OBJECT / APRSPath details**~~ — done in
  `test_long_runtime_aprs_object.py`.  Single ``OBJECT`` line in an
  APRSDIGI block fires its first UI beacon at ~30 s
  (APRSCode.c:1811: ``Timer = ObjectCount * 10 + 30``); test reads
  KISS frames from a PTY-backed RF port, asserts the body and the
  AX.25 destination ``APBPQ1`` (default ``APRSDest``).
- ~~**`FRACK` / `RESPTIME` per-port round-trips**~~ — done in the
  audit's Batch-3 runtime-setter pattern: ``CMD PORT VAL`` → read
  back via ``CMD PORT``, asserting ``PORTVAL`` round-trip.  No
  cfg → runtime scaling assumed.

## Standing target: drive tests through public interfaces only

Some tests reach for an internal implementation detail to assert
on — reading a private struct field, grepping a debug-log line,
inspecting an internal cfg-file rewrite — when an equivalent
public-interface check would do.  Internal-detail assertions go
red on routine refactors that don't change observable behaviour;
they're brittle and they leak implementation into the test suite.

Standing task: sweep through `tests/integration/`, identify each
place a test relies on internals, and rewrite to use only what a
real client would observe — telnet output, JSON API responses,
HTTP body content, AGW frames, KISS frames, file presence/content
under the work directory.  Where the public surface really is
inadequate (e.g. observing log-line side effects because no
runtime command exposes the state), call it out in the test
docstring rather than silently coupling.

The goal is that a non-trivial refactor of `BBSUtilities.c` /
`config.c` / etc. doesn't break tests as long as the wire
behaviour is preserved.

## Coverage target: every command in `docs/node-commands.md`

`docs/node-commands.md` is the reference for the node-prompt
command surface (`COMMANDS[]` in `Cmd.c`).  The standing target is
that **every entry in that document has at least one integration
test** — even if the test only locks in a "rejected with this
specific error" invariant.  The doc is the spec; tests prove the
binary matches.

When adding tests, prefer to land them in test files grouped by
theme rather than per-command (e.g.
`test_telnet_readonly.py` already covers VERSION / NODES / ROUTES /
LINKS / USERS / STATS / MHEARD / `?` / STREAMS as parametrised
rows).  When closing a coverage gap from `node-commands.md`, leave
a comment in the test pointing at the section anchor so a reader
can find the spec quickly.

First audit pass landed: see
[`test-coverage-audit.md`](test-coverage-audit.md).  Currently 112 /
115 commands covered; the remaining 3 (`FINDBUFFS`, `*** LINKED`,
`..FLMSG`) are out-of-scope for telnet integration tests by
design — they'd need either debug-log parsing (rejected) or a
fake BPQ host-stream client (significant new infrastructure for
two niche commands).

When adding a new test
that exercises a node-prompt command, check whether the doc's
entry needs updating (empirical findings sometimes diverge from
the AI-generated wording — see e.g. the `BYE` clarification
landed earlier).

## Spec references

When writing tests that need to construct or parse wire frames,
prefer the canonical specs over re-deriving framing details from
the linbpq source — the spec is the contract; linbpq is just one
implementation of it.

**Mirrored at [packethacking/ax25spec](https://github.com/packethacking/ax25spec):**

- AX.25 link-layer protocol (frame format, address fields, CTL,
  PID).
- KISS TNC spec (FEND / FESC / TFEND / TFESC framing, command
  byte layout).
- Multi-Drop KISS / ackmode extensions.
- FBB forwarding protocol (relevant for the deferred cross-instance
  BBS-to-BBS auto-forwarding tests).

**Packet Network Monitoring Project** — protocol used by linbpq's
node-map / node-status reporting client (M0LTE map, NodeMapTest
historical sources):

- <https://github.com/M0LTE/node-api/blob/master/Tests/Packet_Network_Monitoring_Project_v0.8a.txt>
  is the latest revision.  The folder also has older revisions; the
  latest is not guaranteed to match what's actually deployed, so
  cross-check against the binary when in doubt.

**RHP (Radio Hosted Protocol)** — minimal implementation in BPQ
exists to support WhatsApp gateways.  Reference white papers (PDFs):

- <https://wiki.oarc.uk/packet:white-papers>

If a test exercises one of these protocols, link to the relevant
section from the test docstring.

## Bugs found while writing tests

If a test reveals a real bug in linbpq — a crash, malformed output,
uninitialised buffer, missing handler, or any other observable
defect that isn't just an undocumented design choice — **file it as
an issue** at <https://github.com/M0LTE/linbpq/issues> with:

- A short title naming the symptom.
- A minimal repro (cfg snippet + the request that triggers it).
- The actual vs. expected response.
- A source pointer (file:line) if you found one.
- A "Found while" line linking back to the test that surfaced it.

Where a test depends on the buggy behaviour for now, leave a comment
in the test pointing at the issue number so the test is easy to
upgrade once the bug is fixed.

## Documentation rewrite (separate stream)

Sibling to the test work: the upstream BPQ documentation lives at
<https://www.cantab.net/users/john.wiseman/Documents/> as a sprawl
of HTM files (`BPQ32 Documents.htm`, `BPQCFGFile.html`,
`BPQAXIP Configuration.htm`, `MailServer.html`, `ChatServer.html`,
`LinBPQGuides.html`, etc.).  The content is authoritative but the
format makes it hard to navigate, search, link to source, or
fact-check against the binary.

Goal: rewrite this material in our own repo as Markdown, organised
around the user's actual journey, fact-checked against the source
and against this test suite, and published as a static site with
[MkDocs Material](https://squidfunk.github.io/mkdocs-material/).

Plan (rough — refine as we go):

1. **Fetch + inventory.**  Pull every linked document from John's
   site, record canonical-source URLs, and build a flat index of
   what exists, what overlaps, and what's stale.
2. **Reorganise the IA.**  Group by audience and task — getting
   started, configuration reference, protocols / interfaces,
   subsystems (BBS / Chat / APRS), troubleshooting — rather than
   the as-found jumble.  Cross-link instead of duplicating.
3. **Rewrite to Markdown.**  Per page: convert HTML, modernise
   the prose, keep the technical content faithful.  Fact-check
   each non-trivial statement against `linbpq` or the
   integration suite.  Where a doc claim disagrees with the
   binary, file or link to a `M0LTE/linbpq` issue and capture
   the empirical truth.
4. **MkDocs Material site.**  Land `mkdocs.yml`, theme config,
   navigation, search.  Build into `site/`; publish via GitHub
   Pages off `gh-pages` (or similar).  Include AI-generated /
   review-needed banners in line with the warning already on
   `docs/node-commands.md`.
5. **CI.**  `mkdocs build --strict` in a workflow alongside the
   integration suite so dead links and stale config land red.
6. **Keep upstream credit.**  Link prominently to John Wiseman's
   originals; this is a re-presentation, not a fork.

This is its own stream of work — orthogonal to the regression
suite — but valuable because the test suite gives us a
fact-checking oracle: "does this claim match what the binary does?"
is now a runnable question.

## Goal

A regression test suite around the `linbpq` daemon that gives high confidence
that any non-trivial internal change preserves observable behaviour.

The tests must:

- Exercise the binary the way real users do, over its actual wire protocols.
- Run cross-platform — Linux, WSL, Windows-with-Docker, macOS — so anyone
  touching the code can validate before they push.
- Be fast enough to run on every change. Target: full suite in
  seconds-to-minutes, not hours.
- Survive internal refactors. A test should fail because behaviour changed,
  not because the code moved.

## Background: what `linbpq` is

`linbpq` is a Linux/Unix port of John Wiseman G8BPQ's BPQ32 packet-radio
node software. It is a long-running daemon (`linbpq`) built from
~150 C source files into a single binary, configured by `bpq32.cfg`. It
implements an AX.25 / NET-ROM packet switch, a BBS, a chat node and an
APRS gateway.

### External interfaces (all candidates for testing)

**Network (TCP / UDP):**

- Telnet → node prompt. Dispatch table is `COMMANDS[]` in `Cmd.c`;
  documented in [`docs/node-commands.md`](node-commands.md).
- HTTP / web → admin pages and BBS web UI (`HTTPcode.c`,
  `BBSHTMLConfig.c`).
- AGW TCP → external API for SoundModem / Direwolf clients
  ([BPQtoAGW][bpqtoagw]).
- KISS over TCP (`kiss.c`, `KISSHF.c`).
- AX.25 over IP (UDP) ([BPQAXIP][bpqaxip]).
- NET/ROM over TCP (`NETROMTCP.c`).
- BPQ Host Mode Emulator (TCP) ([BPQTermTCP][bpqtermtcp]).
- MQTT (outbound), CMS / Winlink (outbound).

**Hardware (serial / USB modems):**
HDLC, KISS HF, Pactor (KAM / AEA / HAL / SCS), ARDOP, VARA, FLDigi,
MULTIPSK, WinRPR, HSMODEM. PTY-based simulators required to test
without real radios. Out of scope until network-side tests are mature.

**File-level:**

- `bpq32.cfg` — input.
- `logs/*` — output.
- `*.dat` and `save*.txt` — persistent state, both directions.

[bpqtoagw]: https://www.cantab.net/users/john.wiseman/Documents/BPQtoAGW.htm
[bpqaxip]: https://www.cantab.net/users/john.wiseman/Documents/BPQAXIP%20Configuration.htm
[bpqtermtcp]: https://www.cantab.net/users/john.wiseman/Documents/BPQTermTCP.htm

## Strategy

**Black-box process tests at the real wire interfaces.** Each test:

1. Generates a per-test `bpq32.cfg` in a temp directory with free TCP
   ports chosen at runtime.
2. Spawns `linbpq` as a subprocess.
3. Waits for readiness (TCP probe loop on the configured ports).
4. Drives the daemon through its protocols (telnet, HTTP, AGW, KISS,
   AX/IP).
5. Asserts on responses, on log output, and on persistent-state files.
6. Sends `SIGTERM`, captures the final state, removes the temp directory.

This is the same shape as test suites for postgres, redis, dovecot,
postfix. It works because the wire protocols are externally defined
and stable — the *implementation* can change freely so long as the
wire contract holds.

### Why not unit tests

Unit tests on individual functions in `linbpq` would require sawing
seams into the C code wherever we wanted to test, multiplying surface
area we have to maintain. Refactors would break unit tests for reasons
unrelated to user-visible behaviour. And the most interesting bugs in
this codebase live in the integration between subsystems (AX.25
L2/L3/L4, BBS-over-telnet, link-state propagation) — exactly what
unit tests cannot see.

C-level unit tests stay possible (cmocka) for genuinely-isolated
pure-logic helpers if the need ever arises. They are not the main
effort.

### Why Docker

`linbpq` builds against a non-trivial set of libs (`libpaho-mqtt-dev`,
`libjansson-dev`, `libminiupnpc-dev`, `libconfig-dev`, `libpcap-dev`,
and more). The harness wants Python and pytest. To make the suite
runnable on any developer machine — Linux, WSL, Windows with Docker
Desktop, macOS — the build + test environment is captured in
`docker/Dockerfile.test`. `make test` runs the suite inside that
container.

Native execution stays supported (`make test-native`) for fast
inner-loop iteration when you are already on a Linux box. Docker is
the easy default; native is the fast path.

To bootstrap the native runner once:

```
uv venv tests/.venv
uv pip install --python tests/.venv/bin/python pytest pytest-xdist
```

`tests/.venv/` is gitignored. The makefile prints the bootstrap
command if the venv is missing.

### Continuous integration

The Docker-first design carries straight into GitHub Actions:

- The `ubuntu-latest` runner has Docker pre-installed, so a workflow
  can `docker build -f docker/Dockerfile.test` and
  `docker run --rm <image>` directly. No extra setup steps.
- Image layers cache cleanly via `actions/cache` or `gha` cache
  backend in buildx, which keeps the slow apt-install step out of the
  inner loop after the first run.
- pytest's JUnit-XML output (`--junitxml`) feeds straight into the
  test summary panel; container stdout (linbpq logs, generated
  configs from failing tests) can be uploaded as a workflow artifact
  for post-mortem.
- A matrix can later expand the suite across Debian/Ubuntu versions,
  build flags (`noi2c`, `nomqtt`), or compilers without the workflow
  itself changing shape.
- The same workflow runs the same image you ran locally, removing the
  "passes on my machine, fails in CI" class of issue entirely.

A workflow file (`.github/workflows/tests.yml`) lands as part of
Phase 1 once the harness produces useful output.

## Phased delivery

| Phase | Scope                                                                                                                    | Status |
| ----: | ------------------------------------------------------------------------------------------------------------------------ | ------ |
|     0 | Drop misdirected prior work; confirm `linbpq` builds locally; identify a minimal cfg that boots clean                | done   |
|     1 | `tests/integration/` skeleton + Docker test image + `linbpq_instance` pytest fixture + one telnet smoke test             | done   |
|     2 | Breadth-first interface coverage — telnet, HTTP, AGW, NET/ROM-TCP, FBB-TCP, JSON API; KISS-TCP and AX/IP-UDP deferred  | done\* |
|     3 | Telnet node-command coverage driven by `docs/node-commands.md` (every command, sysop gating, state-changing round-trips) | done\* |
|     4 | BBS + Chat lifecycle — send / read / list / kill mail, chat connect / topic / broadcast                                  | done\* |
|     5 | Persistence round-trip — boot, mutate, shut down, reboot, verify state restored                                          | done\* |
|     6 | Two-instance scenarios via AX/IP UDP — NET/ROM discovery, cross-instance connect, message forwarding                     | done\* |
|     7 | Configuration matrix — minimal / full / edge configs, parse-or-reject assertions                                         | done\* |
|     8 | PTY-based serial-transport tests + modem simulators for KISS-on-serial, ARDOP, VARA, KAM-Pactor, FLDigi, etc.            | done\* |

Phases 0–3 hold most of the value and are achievable in reasonable
time. Phases 6 and 8 are real engineering; do not commit until earlier
phases prove out. Mark progress by updating the table in this file.

\*Phase 2 footnote: AX/IP-over-UDP and KISS-TCP both now have
coverage. AX/IP-UDP gets its own `DRIVER=BPQAXIP` `PORT` block in
the default config plus a canary that the UDP socket binds and
garbage doesn't crash the daemon. KISS-TCP is the *outbound* form —
linbpq as client to a peer over TCP. The peer is typically a
softmodem (Direwolf, UZ7HO) exposing a KISS-TCP listener, or a
serial-to-TCP bridge such as
[m0lte/kissproxy](https://github.com/m0lte/kissproxy) which forwards
a real USB KISS modem (e.g. NinoTNC) onto TCP. A tiny Python TCP
listener stands in as that peer and the test asserts linbpq's
outbound connection is established.

\*Phase 4 footnote: BBS round-trip (SP → Title → Body → /EX → R → K)
plus persistence across reboot, and Chat lifecycle (enter, register
name, /U users, /T topics, /H help) all covered.  Despite
``bpqchat`` shipping as its own binary too, the chat-server code is
linked into ``linbpq`` and turned on by passing ``chat`` on the
command line — confirmed empirically.  Cross-instance forwarding (an
A-side BBS forwarding mail to a B-side BBS) is the natural deeper
test once we want to exercise BBS routing.

\*Phase 3 footnote: covered the read-only commands, per-session settings
round-trip (PACLEN / IDLETIME / L4T1), sysop gating (rejection +
PASSWORD-unlock cycle), and BYE.  Subsequent batches expanded the
coverage further:

- **Subsystem-status commands** — `TELSTATUS` (rejected without port
  number) and `AGWSTATUS` (sockets-table layout) are now locked in.
- **Safe sysop commands** — `SAVEMH` and `VALIDCALLS` covered alongside
  the existing `SAVENODES` test.
- **IP-gateway commands** — `PING` / `ARP` / `IPROUTE` report
  "IP Gateway is not enabled" and `NRR` reports "Not found" with our
  config; locked in so an accidental partial wiring lands red.
- **`LISTEN` / `CQ` / `UNPROTO`** — error responses with no AX.25 port
  available locked in.
- **Application aliases** (`BBS` / `CHAT` / `MAIL`) — return
  "Invalid command" without their respective applications configured.

Still deferred:

- **Connection commands**: the downlink form is fully covered —
  `C <port> <call>`, `CONNECT <port> <call>`, and `NC <port> <call>`
  all exercised on Phase 6's two-instance topology, plus
  `BYE`-from-peer drops the cross-link and returns to the local node
  prompt.  L4-uplink form of CONNECT (`C <call>` with no port, route
  via NODES) is covered too — see
  `test_two_instance.py::test_nodes_propagation_and_l4_uplink_connect`
  ([#4](https://github.com/M0LTE/linbpq/issues/4) closeout).
  ``ATTACH`` is partially covered (audit Batch 2):
  ``ATTACH 99`` → "Invalid Port", ``ATTACH 2`` reaches the attach
  path on a VARA driver via `helpers/vara_modem.py`.  Full attach +
  data through a Pactor / Telnet stream still needs an
  externally-set-up stream — open.
- ~~**`APRS`, `WL2KSYSOP`, `RHP`, `QTSM`, `RADIO`, `UZ7HO`**~~ —
  each subsystem now has at least canary coverage:
  `test_aprs.py` (APRSDIGI), `test_telnet_more_subsystems.py`
  (WL2KSYSOP, QTSM, RADIO), `test_telnet_uz7ho.py` (UZ7HO), audit
  Batch 2 (RHP — header-line canary).
- **`NAT`, `AXRESOLVER`, `AXMHEARD`**: BPQ IP-gateway feature —
  covered by `test_telnet_ip_gateway.py` /
  `test_telnet_ip_gateway_enabled.py`.
- ~~**Side-effect sysop commands**~~ (`REBOOT`, `RESTART`,
  `RESTARTTNC`, `RIGRECONFIG`, `TELRECONFIG`, `STOPCMS` / `STARTCMS`,
  `EXTRESTART`, `STOPROUTE` / `STARTROUTE`, `KISS`) — covered as
  parser-recognition + sysop-gating canaries (audit Batch 1).
  ``STOPROUTE`` / ``STARTROUTE`` exercised behaviourally on
  `test_two_instance.py`.  ``KISS`` exercised against the
  ``PtyKissModem`` PTY in audit Batch 2.
- **Host-protocol pseudo-commands** (`*** LINKED`, `..FLMSG`): only
  meaningful inside a BPQ host stream, not over telnet.

Several entries in `docs/node-commands.md` were re-checked against the
binary while writing these tests; corrections landed in a separate
follow-up commit.

\*Phase 5 footnote: persistence round-trips covered:
- ``BPQNODES.dat`` written by ``SAVENODES`` is loaded on next
  boot in the same dir (no "BPQNODES.dat not found" warning).
- BBS messages survive reboot — post via Phase 4's SP-flow,
  shut down, reboot, and ``R <N>`` returns the title and body
  (``test_persistence.py``).

Open: more state types (chat-room state, MH list cross-reboot
beyond just on-disk presence) — covered as canaries via the BBS
.mes-file presence assertions, deeper round-trips would need
dedicated harnesses.

\*Phase 6 footnote: two-instance over AX/IP-UDP covered:
- Coexistence of two LinbpqInstance daemons in their own
  tempdirs with bidirectional ``MAP`` entries.
- ``ROUTES`` lists the peer on both sides.
- Downlink CONNECT in three syntactic forms (``C 2 N0BBB``,
  ``CONNECT 2 N0BBB``, ``NC 2 N0BBB``) and ``BYE`` returns to
  the local node prompt (``test_two_instance.py``).
- Cross-instance ``CTEXT`` delivery on connect.
- Cross-instance BBS post — A's user posts via downlink-connect
  into B's BBS and the message file lands on B's disk
  (``test_two_instance_bbs.py``).

**NET/ROM discovery** ([#4](https://github.com/M0LTE/linbpq/issues/4))
now resolved at the test-cfg level — root cause was misconfiguration
combined with a parser bug.  Three things are required for NODES
propagation across an AX/IP-UDP link, and the working
`PEER_CONFIG` now sets all three:

- PORT-block `QUALITY=` set to a non-zero value (otherwise
  `L3Code.c:823` skips the port for NODES emit).
- `BROADCAST NODES` line in the BPQAXIP CONFIG block (so "NODES"
  is in `BroadcastAddresses`).
- `B` flag on the `MAP <peer>` entry (so `BCFlag` is set on that
  arp-table entry; without it `bpqaxip.c:658` skips broadcast
  fan-out to that peer).

Plus a static `ROUTES:` neighbour entry for the bootstrap.  The
older comma-separated `<call>,<qual>,<port>` form works correctly;
the keyword=value form was *misparsed*
([#12](https://github.com/M0LTE/linbpq/issues/12)) — separator set
inconsistency in `config.c:1619`.

`test_two_instance.py::test_nodes_propagation_and_l4_uplink_connect`
locks in the working topology: SENDNODES on both sides, ~3s wait,
then NODES tables list the peer and `C N0BBB` (no port) connects
via NET/ROM uplink.
- ~~**Two real BBS instances forwarding to each other**~~ — done in
  ``test_two_instance_bbs_forwarding.py``.  ConnectScript ``["C 2
  N0BBB", "BBS"]`` (connect to NODECALL on AXIP port, then enter
  the BBS application) drives a successful FBB exchange between
  two real BPQMail daemons over AX/IP-UDP — A's user posts a P
  message addressed @ a partner BBS, A's forwarding scheduler
  fires (FwdInterval=2 s), the script dials B, SIDs are exchanged,
  the message is FC-proposed, accepted, B2-compressed body lands,
  and B uncompresses + stores under ``Mail/m_*.mes`` with the
  expected header (MID, From, To, Subject, Body).  ~36 s wall-clock.

  The fake-FBB-partner harness in ``test_bbs_forwarding.py`` +
  ``helpers/fbb_partner.py`` is kept alongside — it remains the
  right tool for fine-grained protocol behaviour (per-flag SID
  variants, spec-violation handling, mode fallbacks etc.) and is
  reusable from other projects.

**FBB inter-BBS forwarding** (issue #4) coverage landed as
``test_bbs_forwarding.py`` plus ``helpers/fbb_partner.py`` (a
Python-side fake BBS that talks the protocol over the wire) and
``helpers/bpqmail_cfg.py`` (renders ``linmail.cfg`` with a
forwarding-partner entry covering every option from the FwdDetail
web-config screen).  Tests are spec-driven, citing the
[FBB protocol spec](https://github.com/packethacking/ax25spec/blob/main/doc/fbb-forwarding-protocol.md):

- SID exchange — F flag presence ↔ ``allow_blocked``; B/1/2 ↔
  cfg compression flags; B2-implies-B1 suppression rule
  (BBSUtilities.c:9092).  Falling back to MBL when partner SID
  lacks F.
- Empty-queue protocol flow: SID + FF → FQ termination per spec
  §10.1.
- Proposal-block parsing: linbpq sends ``FS <code-per-proposal>``;
  multi-proposal blocks (3 props → 3 codes); spec §6.1.
- Spec-violation handling: oversized From field, non-F commands,
  bad F> checksum.
- Linbpq sends FA/FC proposals when messages are queued for the
  partner.  B2 (FC) proposal carries BID + sizes only; FA carries
  the full To/From/AT inline.
- Accepting a proposal triggers a SOH/STX/EOT framed B2 body.
- Partner-config option matrix: TOCalls, ATCalls, PersonalOnly,
  Enabled (locks in the inbound-vs-outbound asymmetry — Enabled=0
  only suppresses linbpq's outbound dial-out).
- Bulletin direct-match (``@=N0BBB``) routes via CheckABBS first
  clause.

Filed bug found while writing these tests:
[#7](https://github.com/M0LTE/linbpq/issues/7) — HRoutes-based
bulletin routing doesn't queue for the partner (matcher in
``CheckABBS`` lines 3629-3650 should fire, but ``MatchMessageto­BBSList``
returns 0 for ``B @ ALL.EU`` against ``HRoutes = ".EU"``).
Test for the expected behaviour is in place but skipped pending fix.

\*Phase 7 footnote: configuration matrix covered:
- Minimal cfg (truly minimal: SIMPLE/NODECALL/LOCATOR/PORT-block
  only); unknown-keyword tolerance; multi-user; comment styles
  (``;`` clean, ``#`` warned-but-tolerated at top level, both
  clean inside CONFIG); case-insensitive keywords; trailing
  whitespace tolerance.
- Sysop globals round-trip (``L4WINDOW``, ``NODESINTERVAL``,
  ``MINQUAL``); ``INFOMSG:`` block content rendered via INFO
  command; ``PASSWORD=`` PWTEXT challenge round-trip with the
  exact sum-of-chars logic from PWDCMD.
- Per-port tuning round-trip 1:1 (RETRIES / MAXFRAME / PERSIST /
  DIGIFLAG / PACLEN-via-PPACLEN); scaled round-trip for
  TXDELAY / TXTAIL (10ms units).
- Block syntaxes (``IDMSG:`` / ``BTEXT:`` with ``***`` terminator,
  ``IPGATEWAY ... ****``, ``APRSDIGI ... ***``) all parse cleanly.
- Telnet driver options: LOGINPROMPT / PASSWORDPROMPT custom
  strings on the wire, block-level CTEXT after login, LOGGING
  produces the Telnet log file with expected event lines,
  cfg-acceptance canaries for the rest (SECURETELNET,
  DisconnectOnClose, LOCALNET, RELAYAPPL, CMS family).
- LinBPQ Apps Interface: ``CMDPORT`` array + ``C HOST <slot>``
  full bidirectional relay (``test_cmdport.py``).
- LINMAIL / LINCHAT cfg-keyword equivalents to the ``mail`` /
  ``chat`` cli args.
- New extended-form ``APPLICATION n,...`` line registers a
  command word that appears in ``?``.

Still deferred:
- ~~**`FRACK` / `RESPTIME` per-port round-trips**~~ — covered via
  the audit's Batch-3 runtime-setter pattern (``CMD PORT VAL`` →
  read back via ``CMD PORT``); non-trivial cfg→runtime scaling not
  asserted, but the sysop command itself round-trips cleanly.
- **`isRF` / `ISRF`** — informational; no observable runtime
  effect to test against.

\*Phase 8 footnote: serial transport plus the major modem
drivers all have integration coverage now.

**KISS-over-serial**: the
[Multi-Drop KISS spec](https://github.com/packethacking/ax25spec/blob/master/doc/multi-drop-kiss-operation.md)
ACKMODE wire format, basic RX/TX over PTY, and a cross-protocol
PTY → AGW-monitor flow are all locked in (``test_kiss_serial.py``,
``helpers/pty_kiss_modem.py``).

**Modem drivers** — each driver now has dial-out + recognisable
post-connect-byte coverage:

- **VARA** (``test_vara.py`` + ``helpers/vara_modem.py``): two
  adjacent TCP sockets (port + port+1) accept linbpq's connect;
  INIT script with ``MYCALL`` and ``LISTEN ON`` lands on the
  control socket; cfg-block keywords like ``BW2300`` get
  forwarded to the TNC verbatim.
- **ARDOP** (``test_ardop.py``): same wire shape as VARA — reuses
  the VaraModem helper.  Locks in the post-INIT-script
  ``LISTEN TRUE`` (vs VARA's ``LISTEN ON``).
- **FLDigi/FLARQ** (``test_fldigi.py`` + ``helpers/fldigi_modem.py``):
  two non-adjacent sockets (ARQ at ``port``, XML-RPC at
  ``port + 40``).  Cfg requires ``ARQMODE`` to disable default
  KISS/UDP path.  XML-RPC poll fires every second post-connect
  (visible as ``POST /RPC2 HTTP/1.1`` on the control socket).
- **KAM-Pactor** (``test_kam_pactor.py``): serial via PTY;
  driver opens the slave node and starts the term-mode
  initialisation state machine — observable as a CR probe / 
  the ``\xC0Q\xC0`` timeout retry on the master end.
- **HSMODEM** (``test_hsmodem.py`` + ``helpers/udp_listener.py``):
  UDP-attached.  Linbpq sends a 260-byte poll datagram (first
  byte 0x3c, NodeCall in payload) every ~2s to the configured
  ``ADDR`` port; lock that in.  Found
  [issue #6](https://github.com/M0LTE/linbpq/issues/6) — the
  driver SIGSEGVs without ``CAPTURE`` / ``PLAYBACK`` set
  (``SendPoll`` ``strcpy``s NULL).
- **WinRPR** (``test_winrpr.py``): single-socket TCP dial-out
  canary — the SCS-Tracker reply protocol isn't simulated, so
  we only confirm the connect lands.

**Legacy modems** (`test_legacy_modems.py` + `test_multipsk.py`):
canary coverage for the remaining drivers — they boot cleanly
with their `DRIVER=` keyword, log their init banner, and
`AEAPACTOR` writes to the serial port post-init:

- **AEAPactor** (PK-232 family) — serial; opens PTY synchronously
  in `AEAExtInit`, writes init bytes within seconds.
- **SCSPactor** (PTC family) — serial.
- **SCSTracker** (DSP-4100) — serial.
- **TrackeMulti** — serial; shares SCSTRK init banner.
- **HALDriver** (DXP-38 / Clover-II) — serial.
- **MULTIPSK** — TCP single-socket dial-out canary.

Driving each driver's full handshake (cmd: prompt detection,
`MYCALL` round-trip, host-mode entry) needs per-modem fake-TNC
simulators — deferred since none of these modems appear in
GB7RDG's or M0LTE's cfg.

Phase 8 closeout: Sister drivers like KISSHF / FreeData remain
covered only as cfg-acceptance canaries; KISSHF rides the same
`KISSHF` driver as the existing UZ7HO/Direwolf KISS-TCP coverage.

## Repository layout

```
tests/
  integration/
    conftest.py              pytest config, the linbpq_instance fixture
    helpers/
      linbpq_instance.py     spawn / readiness / teardown
      telnet_client.py
      agw_client.py
      kiss_client.py
    fixtures/
      configs/               bpq32.cfg templates
      golden/                golden output for diff tests
    test_smoke.py
    test_telnet_*.py         phase 3, command-by-command
    test_http_*.py
    test_agw_*.py
docker/
  Dockerfile.test
  entrypoint.sh
makefile
  test                       default: runs tests in Docker
  test-native                runs against host-built linbpq
docs/
  node-commands.md           public reference (built into the site)
notes/
  plan.md                    this file (internal — not in mkdocs site)
  test-coverage-audit.md     audit of docs/node-commands.md vs tests
```

## How to add a new test

1. Identify the interface and the protocol-level behaviour you want to
   lock in.
2. If no config template covers your scenario, drop one in
   `tests/integration/fixtures/configs/`.
3. Add a `test_*.py` module. Request the `linbpq_instance` fixture
   (parametrised with your config if needed). Drive the protocol.
   Assert on the outcome.
4. If the test depends on a binary-output format (e.g. AGW frames),
   put the framing in a helper under `tests/integration/helpers/`
   rather than inlining it.
5. Prefer "the response *contains* this string" assertions when exact
   output stability is not guaranteed; reserve golden-file diffs for
   genuinely stable output.

## What was thrown away (and why)

**Pre-existing C test harness** — `tests/unit/cmdlineauth_test.c`,
`tests/unit/nodemaptest_test.c`, `tests/unit/nodemap_fixture_test.c`,
`tests/Makefile`, root `makefile` test target. The targets these
tested — `CmdLineAuth.c` and `NodeMapTest.c` — are *not* compiled
into `linbpq` (see the `OBJS` list in `makefile`). They are
dormant utilities. Investing in tests for them did not move the needle
on the actual goal.

**`plan.md` from earlier handoff** — superseded by this document.

**`CmdLineAuth.c` `GetOneTimePasswordCode` extraction** — kept. A
clean, harmless seam left over from prior work. Reverting it is more
churn than it is worth.

## Deferred — pick up after the security-regression batch

Three streams of work raised in review and explicitly parked
until after the Critical/High security-issue regression tests
(#25–#38) land:

- ~~**Vanilla-BPQ-compat sweep.**~~  Done.  Two-pronged: the
  files whose entire premise is the extraction
  (`test_template_extraction.py`, `test_template_render_matrix.py`)
  carry a module-level ``pytestmark = pytest.mark.fork_only``;
  a ``pytest_collection_modifyitems`` hook in
  ``tests/playwright/conftest.py`` skips those when
  ``LINBPQ_VANILLA=1`` is set in the environment.  The
  remaining incidental ``<!-- Version N`` assertions across
  ``test_chat_web.py`` / ``test_mail_admin.py`` /
  ``test_webmail.py`` / ``test_seeded_data.py`` /
  ``test_node_admin.py`` were dropped in favour of structural
  checks (form/table presence, page titles, branding) that
  hold on both fork and vanilla.  ``_wait_for_bbs_ready``
  switched from polling for ``<!-- Version 6`` to polling
  the linbpq stdout log for ``Mail Started`` (printed by
  ``LinBPQ.c::main`` on both fork and vanilla).  Run against
  upstream with ``LINBPQ_VANILLA=1 LINBPQ_BIN=/path/to/upstream/linbpq pytest tests/playwright/``.

- ~~**CFG snippet boot check**~~  Done in
  ``tests/integration/test_doc_cfg_snippets.py``.  Discovers
  every fenced ``ini`` block under ``docs/**/*.md`` (36
  blocks across 17 files at landing time), classifies each
  as full cfg / fragment / placeholder / systemd unit, wraps
  fragments in a two-port harness (Telnet on port 1, BPQAXIP
  loopback on port 2 so APRS / Digimap / per-port snippets
  bind cleanly), spawns real linbpq with each, and asserts:

  - ``Conversion (probably) successful`` present
  - no ``not recognised - Ignored:`` lines (the parser's
    ground-truth signal for an unknown keyword — emitted from
    config.c:1236 / 2332 / 2960)
  - no ``Bad config record`` (per-driver rejection)
  - no ``Conversion failed`` / ``Missing NODECALL`` /
    ``Please enter a LOCATOR``

  Wired into ``.github/workflows/docs.yml`` as a parallel
  ``cfg-snippets`` job that gates the Pages deploy alongside
  the existing strict mkdocs build.  Doc-only PRs adding a
  bad keyword now fail CI before merge.

- ~~**Smaller cleanups.**~~  Done.  Three sub-items:

  - ``AgwSession`` helper class added to
    ``tests/integration/helpers/agw_client.py`` — wraps
    register / connect / send_data / wait_for / drain_data.
    Migrated the six module-level helpers in
    ``test_two_instance_agw_tunnel.py`` plus the AGW soak loop
    in ``test_soak_leaks.py``.  ``test_agw.py`` /
    ``test_kiss_serial.py`` / ``test_security_regressions.py``
    keep their inline ``AgwClient`` / ``AgwFrame`` calls (one-off
    info-query and crash-safety probes, not the session pattern).

  - Two-instance soak test added in ``test_soak_leaks.py`` as
    ``test_two_instance_axip_no_leak_on_connect_cycles``.
    Cycles ``C 2 N0BBB`` → ``BYE`` from instance A → B over
    AX/IP-UDP, 100 iterations, asserts bounded RSS+FD growth on
    both sides independently.  Marked ``long_runtime``.

  - Spot-check landed in ``notes/upstream-spotcheck.md``.  Two
    real drifts fixed in-place: ``protocols/bpqtoagw.md``
    claimed ``IOADDR`` is hex (parser is decimal-only via
    ``atoi``); ``protocols/axip.md`` listed ``EXCLUDE`` as an
    AXIP CONFIG-block keyword (it's actually a top-level
    keyword in ``config.c:1104``).  Three docs verified clean
    against the C source.  One Linux-vs-Windows behavioural
    subtlety on ``PROMISCUOUS`` flagged but not changed.

## Open questions and risks

- **Setcap requirement.** The build runs
  `setcap CAP_NET_ADMIN,CAP_NET_RAW,CAP_NET_BIND_SERVICE` on the
  binary. Test scenarios should avoid features needing raw sockets or
  low ports. Confirm this is achievable with telnet + HTTP + AGW +
  KISS-TCP + AX/IP-UDP all on high ports.
- **Readiness detection.** First version uses a TCP probe loop. If
  startup is slow on a constrained CI box this may need a stdout
  sentinel.
- **Free port selection.** `socket.bind(('127.0.0.1', 0))` then close;
  small TOCTOU window, fine on a single host.
- **Inter-test isolation.** Each test gets its own tempdir and its own
  linbpq instance. Slow but unambiguous. Consider session-scoped
  fixtures only after profiling.
- **Hardware modem coverage** is genuinely hard and may stay out of
  scope indefinitely.
