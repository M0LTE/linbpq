/*
 * test_inp3_unsigned_comparison.c
 *
 * Verify that the RTT bounds check in ProcessRTTReply correctly handles
 * all uint32_t values.  The original code used:
 *
 *     if (RTT > 60000 || RTT < 0)
 *
 * Because RTT is uint32_t the "RTT < 0" arm is always false (unsigned
 * values are never negative).  The simplified check is:
 *
 *     if (RTT > 60000)
 *
 * This also catches the wrap-around case (e.g. 0xFFFFFFFF) that the
 * dead "< 0" comparison was presumably meant to cover.
 */

#include <stdint.h>
#include <stdio.h>

/* Mirrors the fixed bounds check from BPQINP3.c ProcessRTTReply. */
static int rtt_is_rejected(uint32_t RTT)
{
    return RTT > 60000;
}

int main(void)
{
    int failures = 0;

    /* Case 1: RTT = 0 -- valid, should NOT be rejected */
    if (rtt_is_rejected(0)) {
        fprintf(stderr, "FAIL: RTT=0 was rejected\n");
        failures++;
    }

    /* Case 2: RTT = 1 -- valid, should NOT be rejected */
    if (rtt_is_rejected(1)) {
        fprintf(stderr, "FAIL: RTT=1 was rejected\n");
        failures++;
    }

    /* Case 3: RTT = 60000 -- boundary, should NOT be rejected */
    if (rtt_is_rejected(60000)) {
        fprintf(stderr, "FAIL: RTT=60000 was rejected\n");
        failures++;
    }

    /* Case 4: RTT = 60001 -- too high, should be rejected */
    if (!rtt_is_rejected(60001)) {
        fprintf(stderr, "FAIL: RTT=60001 was not rejected\n");
        failures++;
    }

    /* Case 5: RTT = 0xFFFFFFFF -- wrapping case, caught by > 60000 */
    if (!rtt_is_rejected(UINT32_C(0xFFFFFFFF))) {
        fprintf(stderr, "FAIL: RTT=0xFFFFFFFF was not rejected\n");
        failures++;
    }

    if (failures == 0) {
        printf("All tests passed.\n");
        return 0;
    }

    fprintf(stderr, "%d test(s) failed.\n", failures);
    return 1;
}
