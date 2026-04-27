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
| Covered    |   112 |
| Uncovered  |     3 |
| **Total**  | **115** |

## Uncovered (3) — out of scope for telnet integration tests

| Command       | Reason |
|---------------|--------|
| `FINDBUFFS`   | Writes to debug log only; no observable effect on a telnet session. Covering it would require parsing the linbpq debug log, which we deliberately avoid (see plan.md "drive tests through public interfaces only"). |
| `*** LINKED`  | Host-protocol pseudo-command. Only meaningful when the client is a BPQ host stream (not a normal telnet user); the dispatcher recognises it but it has no telnet semantics. |
| `..FLMSG`     | Same as `*** LINKED` — host-protocol pseudo-command. |

## What landed

Three batches brought the audit from the pre-audit baseline of 55 /
115 to 112 / 115:

### Batch 1 — Tier 1 / Tier 2 (~46 tests)

- **Tier 1**: MHEARD filter variants `MHL` / `MHU` / `MHV` / `MHLV` /
  `MHUV`, `LIS` abbreviation, spelt-out `HELP`, `QUIT` alias of
  `BYE`. Added to `test_telnet_readonly.py` and `test_telnet_bye.py`.
- **Tier 2 sysop globals**: `OBSINIT`, `OBSMIN`, `L3TTL`,
  `L4RETRIES`, `IDINTERVAL`, `FULLCTEXT`, `HIDENODES`, `L4DELAY`,
  `BTINTERVAL`, `MAXHOPS`, `PREFERINP3`, `DEBUGINP3`, `MONTOFILE`,
  `L4TIMEOUT` (global), `MAXRTT`, `MAXTT`, `RIFINTERVAL`,
  `NODEIDLETIME`. Parametrise rows in `test_config_to_runtime.py`.
- **Tier 2 per-port tunables**: `QUALITY`, `DIGIPORT`, `MAXUSERS`,
  `L3ONLY`, `INP3ONLY`, `ALLOWINP3`, `ENABLEINP3`, `FULLDUP`,
  `SOFTDCD`. Added to `PER_PORT_TUNING` parametrise.
- **Side-effect sysop-gating canaries**: `REBOOT`, `RESTART`,
  `RESTARTTNC`, `RIGRECONFIG`, `TELRECONFIG`, `STOPCMS`, `STARTCMS`,
  `EXTRESTART`. Verify the parser recognises the word and enforces
  the sysop gate without firing the side effect.
- **`STOPROUTE` / `STARTROUTE`**: parametrised against the
  two-instance topology in `test_two_instance.py`.
- **`DUMP` / `EXCLUDE`** (Windows-build commands): parser-recognition
  canary on Linux.

### Batch 2 — fixture-needing (~10 tests)

- **`GETPORTCTEXT`**: pre-write `Port1CTEXT.txt`, run the command,
  assert the response lists port 1.
- **`KISS`**: reuse `helpers/pty_kiss_modem.py`; `KISS 2 6 1 2 3`
  lands FEND-wrapped bytes (`\xC0\x06\x01\x02\x03\xC0`) on the PTY
  master.
- **`RHP`**: dumps Paula G8PZT's Remote Host Protocol session table
  (RHP.c:807). Header line is always emitted — canary for command
  recognition.
- **`ATTACH`**: reuse `helpers/vara_modem.py` for a PROTOCOL=10
  port. `ATTACH 99` rejects "Invalid Port"; `ATTACH 2` reaches the
  attach path on the VARA driver.
- **`POLLNODES`**: negative cases (no port, non-qualified port) in
  single-instance fixture; positive case (qualified AXIP port → "Ok")
  in two-instance topology.
- **`SENDRIF`**: negative (unknown route → "Route not found") in
  single-instance; positive (known neighbour → "Ok") in two-instance.

### Batch 3 — runtime-setter pattern (~5 tests)

For commands without a clean cfg→sysop round-trip (different value
space or non-trivial scaling), exercise the sysop command's
read/write directly: `CMD PORT` → `CMD PORT VAL` → `CMD PORT`,
asserting the value round-trips through `PORTVAL` / `SWITCHVAL`.

- **`FRACK`**, **`RESPTIME`** — per-port byte setters; cfg-side
  scaling differs from runtime-side raw byte, but the sysop command
  itself stores and reads the raw byte cleanly.
- **`XMITOFF`** — port-disable byte; no cfg keyword, but
  setter/getter via sysop works.
- **`BBSALIAS`** — sysop sets a byte directly; cfg uses string enum
  `NOBBS` / `BBSOK`. Different value space, same byte — the sysop
  setter round-trips.
- **`LINKEDFLAG`** — global byte; sysop uses numeric values
  (`LINKEDFLAG 89` for 'Y'); round-trips through `SWITCHVAL`.

## Remaining

The 3 uncovered are out-of-scope for telnet integration tests by
design. Closing any of them would require either reading linbpq's
internal debug log (rejected in plan.md) or implementing a fake
BPQ host-stream client (significant new infrastructure for two
commands that don't surface to ordinary telnet users).

# Public-interface sweep — the test side of the same standing target

Beyond _what_ commands have tests, the standing target is _how_ they
test — drive setup AND assertions through public interfaces only.
Two batches of refactor went in alongside the coverage work above:

## Cleaned

- ``test_persistence.py``: replaced ``BPQNODES.dat`` existence
  check + log-grep ("BPQNODES.dat not found") with public-interface
  round-trip — ``NODES ADD`` a sentinel, ``SAVENODES``, reboot,
  assert sentinel still in ``NODES`` output.  Same test for the BBS
  message-store path: dropped the redundant ``Mail/`` dir / ``.mes``
  file existence checks (the read-back via ``R 1`` proves the
  contract end-to-end already).
- ``test_axip_extras.py``: replaced "bad config record" log grep
  with ``PORTS`` listing assertion.  If the cfg parser had rejected
  the AXIP block, the port wouldn't be listed.
- ``test_legacy_modems.py``, ``test_kam_pactor.py``,
  ``test_kiss_serial.py``: replaced driver-init-banner log greps
  with ``PORTS`` listing assertion against the cfg's ``ID=`` value.

## Acknowledged exceptions (documented, not fixed)

### ``stdout.log`` greps that have no public read-back

Some assertions check that linbpq's cfg parser warned (or didn't)
about a specific keyword. linbpq has no runtime command that
exposes "did you parse keyword X without complaint" — the only
observable surface is the boot log. These are kept and flagged in
the test docstring.

Affected files:
- ``test_config_keyword_acceptance.py`` — "Ignored:KEYWORD" canaries
- ``test_config_matrix.py`` — unknown-keyword-warning assertions
- ``test_telnet_driver_options.py`` — telnet PORT-block keywords
  with no matching read-back command (SECURETELNET, RELAYAPPL, CMS,
  DisconnectOnClose, LOCALNET)
- ``test_config_to_runtime.py::test_cfg_per_port_accepted_canary`` —
  per-port keywords with no matching read-back

Closing these would need linbpq itself to expose a "cfg-parser
warnings" command or API endpoint.

### ``linmail.cfg`` writes for BBS-forwarding test setup

``helpers/bpqmail_cfg.py`` and ``test_bbs_forwarding.py`` write
``linmail.cfg`` directly to seed BPQMail's forwarding-partner cfg
(BBSForwarding section + BBSUsers F_BBS entry).  Strictly speaking,
``linmail.cfg`` is BPQMail's persisted state, not a hand-edit
config — the public-interface alternative is the BPQMail web UI's
``/Mail/FWDSave`` POST endpoint plus user-creation via
``/Mail/UserSave``.

Why we don't drive the web UI today:

- The web UI auth flow is session-key-based with HTML-form-driven
  login.  Reverse-engineering the form encoding is a non-trivial
  scripting exercise.
- Tests would be substantially slower (multiple HTTP round-trips
  per test setup).
- The forwarding-partner USER record needs to exist before
  ``/Mail/FWDSave`` works; that requires an extra create-user step.
- The fake-FBB-partner coverage in ``test_bbs_forwarding.py`` already
  exercises both sides of the FBB protocol; the test-setup format
  doesn't change what's verified at the wire layer.

**Better long-term path — add a JSON API endpoint.**  A clean
``POST /api/v1/mail/forwarding`` (or similar) that accepts a JSON
body describing partner cfg would serve both the UI (replacing the
form-encoded ``/Mail/FWDSave``) and integration tests (replacing
the direct ``linmail.cfg`` write).  Cleanest fix for both
audiences; flagged here as a future task.

Until then, the ``linmail.cfg`` write is acknowledged as an
acceptable-but-imperfect pattern, justified by:
- It's textually minimal (~50 LoC of helper)
- It exercises the cfg-loader path on every boot (some test value)
- Refactoring later doesn't invalidate the existing FBB-protocol
  assertions

## ``Port<N>CTEXT.txt`` writes — legitimate test input

``test_telnet_sysop.py::test_getportctext_reads_per_port_files``
writes a ``Port1CTEXT.txt`` file before invoking ``GETPORTCTEXT``.
This isn't seeding internal state — it's the documented input
format that ``GETPORTCTEXT`` re-reads, so writing the file is part
of testing the public command.  No refactor needed.

## ``bpq32.cfg`` writes — daemon configuration

Every test writes a ``bpq32.cfg`` to the work directory before
booting linbpq.  This is the daemon's primary configuration
interface; tests pre-writing it is analogous to a sysop editing it
by hand.  Not "implementation detail leakage" — required input to
the daemon.
