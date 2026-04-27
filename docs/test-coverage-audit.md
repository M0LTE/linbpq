# Test coverage audit — `docs/node-commands.md`

This is a snapshot audit of which entries in
[`node-commands.md`](node-commands.md) have integration-test coverage
in `tests/integration/`. The standing target (see `plan.md`) is for
every command in the doc to have at least one test that exercises it
through linbpq's public interfaces.

## Methodology

The audit script walks every detailed-reference and quick-reference
entry in `node-commands.md`, then greps test code for patterns that
indicate the command is actually executed against the node prompt:

- `run_command("CMD ...")` / `write_line("CMD ...")` / `send_line(b"CMD ...")`
- `pytest.param("CMD ...", ...)` rows in parametrised tests

Mentions in comments or docstrings, or use as a cfg keyword (e.g.
`MINQUAL=128` in a config-file), do not count as command coverage.

## Summary

| Category   | Count |
|------------|------:|
| Covered    |   101 |
| Uncovered  |    14 |
| **Total**  | **115** |

(Audited at the commit that lands this doc.)

## Uncovered (14)

All remaining gaps need fixtures we don't have, store fields without a
clean cfg-keyword round-trip, or are out-of-scope for the integration
suite. None of the easy gaps remain.

### Need a fixture or external state

| Command       | What's needed |
|---------------|---------------|
| `ATTACH`      | Pactor / VARA / Telnet stream attach. Needs an externally-set-up TNC session. |
| `RHP`         | Routing Hash Protocol — needs RHP listener configured. |
| `POLLNODES`   | INP3 nodes-poll. Needs an INP3-capable peer. |
| `SENDRIF`     | INP3 RIF send. Same fixture need as `POLLNODES`. |
| `KISS`        | Sends raw KISS bytes. Could verify a configured KISS port (PTY) receives them — fixture exists in `helpers/pty_kiss_modem.py`, just no test. |
| `GETPORTCTEXT`| Re-reads `PortNCTEXT.txt` files. Needs pre-written files + a way to verify they were re-read. |

### No clean cfg-keyword round-trip

These have a sysop read-back command but no cfg keyword that maps 1:1
to the same byte. Coverage would need a different test strategy
(setter-then-getter inside one session, or a runtime-only assertion).

| Command     | Notes |
|-------------|-------|
| `FRACK`     | Cfg `FRACK=` is in milliseconds; sysop reports a scaled byte. Non-trivial scaling (FRACK=2000 → 6, FRACK=3300 → 9). Already noted as deferred in plan.md Phase 7 footnote. |
| `RESPTIME`  | Same shape as `FRACK`. |
| `XMITOFF`   | Maps to `PORTDISABLED`; no cfg keyword sets this directly. |
| `BBSALIAS`  | Sysop command sets a byte; cfg `BBSFLAG=` takes a string enum (`NOBBS` / `BBSOK`) — different value space. |
| `LINKEDFLAG`| Sysop reads a byte; cfg `ENABLE_LINKED=` takes a single character (`A` / `Y`) — different value space. |

### Out of scope

| Command       | Reason |
|---------------|--------|
| `FINDBUFFS`   | Writes to debug log; no observable telnet effect. |
| `*** LINKED`  | Host-protocol pseudo-command, not for telnet. |
| `..FLMSG`     | Same — host-protocol pseudo-command. |

## What landed

This audit pass added the following coverage (compared to the pre-audit
baseline of 55 covered / 60 uncovered):

- **Tier 1** (~7 commands): MHEARD filter variants `MHL`/`MHU`/`MHV`/
  `MHLV`/`MHUV`, `LIS` abbreviation, spelt-out `HELP`, `QUIT` alias of
  `BYE`. Added to `test_telnet_readonly.py` and `test_telnet_bye.py`.
- **Tier 2 sysop globals** (~13 commands): `OBSINIT`, `OBSMIN`,
  `L3TTL`, `L4RETRIES`, `IDINTERVAL`, `FULLCTEXT`, `HIDENODES`,
  `L4DELAY`, `BTINTERVAL`, `MAXHOPS`, `PREFERINP3`, `DEBUGINP3`,
  `MONTOFILE`, `L4TIMEOUT` (global form), `MAXRTT`, `MAXTT`,
  `RIFINTERVAL`, `NODEIDLETIME`. Added as parametrise rows in
  `test_config_to_runtime.py`.
- **Tier 2 per-port tunables** (~10 commands): `QUALITY`, `DIGIPORT`,
  `MAXUSERS`, `L3ONLY`, `INP3ONLY`, `ALLOWINP3`, `ENABLEINP3`,
  `FULLDUP`, `SOFTDCD`. Added to `PER_PORT_TUNING` parametrise.
- **Side-effect sysop-gating canaries** (~8 commands): `REBOOT`,
  `RESTART`, `RESTARTTNC`, `RIGRECONFIG`, `TELRECONFIG`, `STOPCMS`,
  `STARTCMS`, `EXTRESTART`. Verify the parser recognises the word and
  enforces the sysop gate without firing the side effect.
- **`STOPROUTE` / `STARTROUTE`**: parametrised against the two-instance
  topology in `test_two_instance.py`.
- **`DUMP` / `EXCLUDE`** (Windows-build commands): parser-recognition
  canary on Linux.

## Remaining action plan

The 14 uncovered are genuinely deferred work:

- The 6 fixture-needing commands warrant their own per-feature test
  files; pursue when a deployment needs that command path verified.
  `KISS` is the cheapest of these — the PTY fixture already exists.
- The 5 no-clean-round-trip commands could be covered by adding a
  *runtime setter* test pattern (e.g. `LINKEDFLAG Y` then read back),
  or just left as-is — they're sysop tunables that are unlikely to
  drift.
- The 3 out-of-scope entries stay out by design.
