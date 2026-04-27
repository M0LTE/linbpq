# LinBPQ regression test plan

> Living document. Update as the suite grows or the strategy shifts.

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
node software. It is a long-running daemon (`linbpq.bin`) built from
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
2. Spawns `linbpq.bin` as a subprocess.
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
|     0 | Drop misdirected prior work; confirm `linbpq.bin` builds locally; identify a minimal cfg that boots clean                | done   |
|     1 | `tests/integration/` skeleton + Docker test image + `linbpq_instance` pytest fixture + one telnet smoke test             | done   |
|     2 | Breadth-first interface coverage — telnet, HTTP, AGW, NET/ROM-TCP, FBB-TCP, JSON API; KISS-TCP and AX/IP-UDP deferred  | done\* |
|     3 | Telnet node-command coverage driven by `docs/node-commands.md` (every command, sysop gating, state-changing round-trips) | done\* |
|     4 | BBS + Chat lifecycle — send / read / list / kill mail, chat connect / topic / broadcast                                  | done\* |
|     5 | Persistence round-trip — boot, mutate, shut down, reboot, verify state restored                                          | started |
|     6 | Two-instance scenarios via AX/IP UDP — NET/ROM discovery, cross-instance connect, message forwarding                     | started |
|     7 | Configuration matrix — minimal / full / edge configs, parse-or-reject assertions                                         | started |
|     8 | PTY-based modem simulators for KISS HF, ARDOP, VARA, KAM, etc.                                                           | todo   |

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
linked into ``linbpq.bin`` and turned on by passing ``chat`` on the
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

- **Connection commands**: the downlink form is fully covered now —
  `C <port> <call>`, `CONNECT <port> <call>`, and `NC <port> <call>`
  all exercised on Phase 6's two-instance topology, plus
  `BYE`-from-peer drops the cross-link and returns to the local node
  prompt.  Still deferred: `ATTACH` (Pactor / VARA / Telnet stream
  attach — needs an externally-set-up stream) and the **L4-uplink
  form of CONNECT** (`C <call>` with no port, route via NODES).
  Empirically, `SENDNODES` between two AX/IP-UDP-linked instances
  doesn't seem to actually propagate the NODES table within a
  reasonable test window — needs deeper investigation, likely an
  issue around AX/IP carrying NETROM frames or NODES-broadcast
  prerequisites we haven't met.
- **`APRS`, `WL2KSYSOP`, `RHP`, `QTSM`, `RADIO`, `UZ7HO`**: each needs
  its own subsystem configured.
- **`NAT`, `AXRESOLVER`, `AXMHEARD`**: BPQ IP-gateway feature.
- **Side-effect sysop commands** (`REBOOT`, `RESTART`, `RESTARTTNC`,
  `RIGRECONFIG`, `TELRECONFIG`, `STOPPORT` / `STARTPORT`,
  `STOPCMS` / `STARTCMS`, `STOPROUTE` / `STARTROUTE`, `KISS`): carry
  side effects we should not casually trigger; need fixtures that
  explicitly invite restart-style behaviour.
- **Host-protocol pseudo-commands** (`*** LINKED`, `..FLMSG`): only
  meaningful inside a BPQ host stream, not over telnet.

Several entries in `docs/node-commands.md` were re-checked against the
binary while writing these tests; corrections landed in a separate
follow-up commit.

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
  plan.md                    this file
  node-commands.md
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
into `linbpq.bin` (see the `OBJS` list in `makefile`). They are
dormant utilities. Investing in tests for them did not move the needle
on the actual goal.

**`plan.md` from earlier handoff** — superseded by this document.

**`CmdLineAuth.c` `GetOneTimePasswordCode` extraction** — kept. A
clean, harmless seam left over from prior work. Reverting it is more
churn than it is worth.

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
