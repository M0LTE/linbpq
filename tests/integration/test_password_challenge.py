"""``PASSWORD=`` cfg keyword and the non-Secure_Session challenge.

For users who weren't logged in via a SYSOP-flagged ``USER=`` line,
``PASSWORD`` at the node prompt does NOT short-circuit to "Ok" —
instead PWDCMD generates 5 random 1-based positions into the
configured ``PWTEXT`` and prints them.  The user is expected to
look up the characters at those positions and reply with the
five-character string.

PWDCMD's check (``Cmd.c::PWDCMD`` around line 1232) is:

```c
n = 5;
while (n--)
    pwsum += *(ptr++);
if (Session->PASSWORD == pwsum) ...
```

i.e. it sums the ASCII bytes of the user's reply and compares
against the sum stored when the challenge was issued.

The test drives the full math: receive challenge → compute
reply from known PWTEXT → submit → assert "Ok".
"""

from __future__ import annotations

import re
import socket
import time
from pathlib import Path
from string import Template

from helpers.linbpq_instance import LinbpqInstance
from helpers.telnet_client import TelnetClient


# Use a known PWTEXT.  PWDCMD picks indexes via ``rand() % PWLen``,
# so longer/wider strings give more entropy but for our purposes
# any string covering ASCII 'A'..'Z' is fine.
PWTEXT = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


CFG_WITH_PWTEXT = Template(
    f"""\
SIMPLE=1
NODECALL=N0CALL
NODEALIAS=TEST
LOCATOR=NONE
PASSWORD={PWTEXT}

PORT
 ID=Telnet
 DRIVER=Telnet
 CONFIG
 TCPPORT=$telnet_port
 HTTPPORT=$http_port
 MAXSESSIONS=10
 USER=test,test,N0CALL,,SYSOP
 USER=plain,plain,M0LTE,,
ENDPORT
"""
)


def test_non_sysop_password_challenge_round_trip(tmp_path: Path):
    """Non-sysop user runs PASSWORD; we parse the 5 positions from
    the response, compute the expected reply from the configured
    PWTEXT, send it back, and assert the daemon replies "Ok"."""
    with LinbpqInstance(tmp_path, config_template=CFG_WITH_PWTEXT) as linbpq:
        with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
            client.login("plain", "plain")

            # Challenge: 5 numbers separated by spaces.
            client.write_line("PASSWORD")
            challenge = client.read_idle(idle_timeout=1.0, max_total=3.0)
            match = re.search(rb"(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)", challenge)
            assert match, (
                f"no 5-number challenge in: {challenge!r}"
            )
            positions = [int(g) for g in match.groups()]

            # Compute reply: PWTEXT[pos-1] for each position
            # (positions are 1-based — see Cmd.c:1295 ``%d %d ...``
            # printed after each ``p1++``).
            reply = "".join(PWTEXT[p - 1] for p in positions)

            # Reply with the second PASSWORD command, the 5 characters
            # as the argument.  PWDCMD parses ``CmdTail`` for the reply
            # token (Cmd.c:1248).
            client.write_line(f"PASSWORD {reply}")
            response = client.read_idle(idle_timeout=1.0, max_total=3.0)

    assert b"Ok" in response, (
        f"PASSWORD challenge reply not accepted (positions={positions}, "
        f"reply={reply!r}): {response!r}"
    )


def test_password_challenge_wrong_reply_rejected(tmp_path: Path):
    """A reply of the wrong length / wrong characters is rejected
    rather than granting sysop status.  We deliberately reply with
    five zeros — the sum of those is unlikely to equal any random
    challenge sum (zeros add 0x30*5 = 240; valid replies for the
    A..Z PWTEXT sum 65*5..90*5 = 325..450)."""
    with LinbpqInstance(tmp_path, config_template=CFG_WITH_PWTEXT) as linbpq:
        with TelnetClient("127.0.0.1", linbpq.telnet_port) as client:
            client.login("plain", "plain")
            client.write_line("PASSWORD")
            client.read_idle(idle_timeout=1.0, max_total=3.0)
            client.write_line("PASSWORD 00000")
            response = client.read_idle(idle_timeout=1.0, max_total=3.0)

            # Then try a sysop command — should still be gated.
            sysop_resp = client.run_command("SAVENODES")

    assert b"Ok" not in response.split(b"\r")[0], (
        f"wrong reply accepted: {response!r}"
    )
    assert b"Command requires SYSOP status" in sysop_resp, (
        f"expected sysop gate still active: {sysop_resp!r}"
    )
