/*
 * Unit test for the QTSMCMD NULL-deref guard.
 *
 * In Cmd.c::QTSMCMD (around line 6571) the upstream 6.0.25.28 merge
 * added a "QTSM HELP" subcommand by calling _stricmp() on the result
 * of strtok_s() without a NULL check:
 *
 *     ptr = strtok_s(CmdTail, " ,\r", &context);
 *     if (_stricmp(ptr, "HELP") == 0)   // ptr may be NULL
 *
 * When the user issues a bare "QTSM" (no arguments), CmdTail has no
 * token, strtok_s() returns NULL, and _stricmp(NULL, ...) segfaults
 * the user session.  atoi(NULL) on the next line is also undefined.
 *
 * The fix replaces a NULL token with an empty string, so the
 * handler falls through to the existing "Error - Port 0 is not a
 * KISS port" reply path without crashing.  This test exercises the
 * corrected dispatch logic in isolation against the inputs that
 * used to trigger the crash.
 *
 * See https://github.com/M0LTE/linbpq/issues/64.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>

/* ---- Extracted dispatch logic (mirrors Cmd.c:6571..6585 + guard) ---- */

static int qtsm_dispatch(char *cmd_tail)
{
    char *context = NULL;
    char *ptr = strtok_r(cmd_tail, " ,\r", &context);
    int port;

    if (ptr == NULL)
        ptr = "";

    if (strcasecmp(ptr, "HELP") == 0)
        return -1;                  /* HELP path */

    port = atoi(ptr);
    return port;                    /* falls through to PORT lookup */
}

/* ---- Test harness ------------------------------------------------ */

static int failures = 0;

static void check(const char *label, int expected, int actual)
{
    if (actual == expected) {
        printf("PASS  %s: got %d\n", label, actual);
    } else {
        printf("FAIL  %s: expected %d, got %d\n", label, expected, actual);
        failures++;
    }
}

int main(void)
{
    char buf[64];

    /* Bug repro: bare QTSM (empty CmdTail) used to NULL-deref via
       _stricmp / atoi.  With the guard, dispatch returns port 0 and
       the real handler emits "Error - Port 0 is not a KISS port". */
    strcpy(buf, "");
    check("bare QTSM", 0, qtsm_dispatch(buf));

    /* All-whitespace tail produced NULL the same way. */
    strcpy(buf, "   ");
    check("whitespace-only tail", 0, qtsm_dispatch(buf));

    /* HELP subcommand still reachable. */
    strcpy(buf, "HELP");
    check("HELP (uppercase)", -1, qtsm_dispatch(buf));

    strcpy(buf, "help");
    check("help (lowercase)", -1, qtsm_dispatch(buf));

    /* Normal port number with trailing args still parses. */
    strcpy(buf, "5 il2p only");
    check("port 5 with args", 5, qtsm_dispatch(buf));

    if (failures) {
        printf("%d failures\n", failures);
        return 1;
    }
    printf("OK\n");
    return 0;
}
