# Test coverage audit — `docs/node-commands.md`

This is a snapshot audit of which entries in
[`node-commands.md`](node-commands.md) have integration-test coverage
in `tests/integration/`. The standing target (see `plan.md`) is for
every command in the doc to have at least one test that exercises it
through linbpq's public interfaces.

## Methodology

Audit script walks every detailed-reference and quick-reference
entry in `node-commands.md`, then greps test code for patterns that
indicate the command is actually executed against the node prompt:

- `run_command("CMD ...")` / `write_line("CMD ...")` / `send_line(b"CMD ...")`
- `pytest.param("CMD ...", ...)` rows in parametrised tests

Mentions in comments or docstrings, or use as a cfg keyword (e.g.
`MINQUAL=128` in a config-file), do not count as command coverage.

## Summary

| Category   | Count |
|------------|------:|
| Covered    |   107 |
| Uncovered  |     8 |
| **Total**  | **115** |

## Uncovered (8)

All remaining gaps are either out-of-scope for the integration
suite or have no clean wire-observable round-trip path.

### No clean cfg-keyword round-trip

These have a sysop read-back command but no cfg keyword that maps 1:1
to the same byte. Coverage would need a different test strategy
(setter-then-getter inside one session, or a runtime-only assertion
that doesn't compare against cfg).

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
| `FINDBUFFS`   | Writes to debug log only; no observable telnet effect. |
| `*** LINKED`  | Host-protocol pseudo-command, not for telnet. |
| `..FLMSG`     | Same — host-protocol pseudo-command. |

## What landed

Two batches of work bring the audit to 107/115. The pre-audit
baseline was 55/115; the first audit pass added 46 tests reaching
101/115; the fixture-needing pass added 6 more reaching 107/115.

### First audit pass (Tier 1 + Tier 2)

- **Tier 1** (~7 commands): MHEARD filter variants `MHL`/`MHU`/`MHV`/
  `MHLV`/`MHUV`, `LIS` abbreviation, spelt-out `HELP`, `QUIT` alias of
  `BYE`. Added to `test_telnet_readonly.py` and `test_telnet_bye.py`.
- **Tier 2 sysop globals** (~18 commands): `OBSINIT`, `OBSMIN`,
  `L3TTL`, `L4RETRIES`, `IDINTERVAL`, `FULLCTEXT`, `HIDENODES`,
  `L4DELAY`, `BTINTERVAL`, `MAXHOPS`, `PREFERINP3`, `DEBUGINP3`,
  `MONTOFILE`, `L4TIMEOUT` (global form), `MAXRTT`, `MAXTT`,
  `RIFINTERVAL`, `NODEIDLETIME`. Parametrise rows in
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

### Fixture-needing pass

- **`GETPORTCTEXT`**: writes `Port1CTEXT.txt` to the work dir, runs
  the command, asserts the response lists port 1.  Negative case
  (no files present) also covered.
- **`KISS`**: reuses `helpers/pty_kiss_modem.py` to give linbpq a
  KISS-async serial port; runs `KISS 2 6 1 2 3` (sysop) and asserts
  the FEND-wrapped bytes (`\xC0\x06\x01\x02\x03\xC0`) land on the
  PTY master.
- **`RHP`**: dumps Paula G8PZT's Remote Host Protocol session table
  (RHP.c:807).  Header line is always emitted — canary for
  command recognition.  No RHP listener needed.
- **`ATTACH`**: reuses `helpers/vara_modem.py` for a PROTOCOL=10
  port; runs `ATTACH 99` (rejects "Invalid Port"), then `ATTACH 2`
  (reaches the attach path — fake VARA TNC's lack of full handshake
  surfaces as "Error - TNC Not Ready", which is itself a recognised
  response).
- **`POLLNODES`**: negative cases (no port → "Invalid Port"; non-
  qualified port → "Quality = 0 or INP3 Port") in single-instance
  fixture; positive case (qualified AXIP port → "Ok") in
  two-instance topology.
- **`SENDRIF`**: negative case (unknown route → "Route not found")
  in single-instance; positive case (known neighbour → "Ok") in
  two-instance.

## Remaining action

The 8 uncovered are genuinely deferred work:

- The 5 no-clean-round-trip commands could be covered by adding a
  *runtime setter* test pattern (e.g. `LINKEDFLAG Y` then read back),
  or just left as-is — they're sysop tunables that are unlikely to
  drift.
- The 3 out-of-scope entries stay out by design.

If full coverage is required, the runtime-setter pattern is the
straightforward way: send the command with a value, then send it
without arguments to read back, assert the value matches. This
doesn't depend on cfg-loading behaviour and would close the
remaining 5.
