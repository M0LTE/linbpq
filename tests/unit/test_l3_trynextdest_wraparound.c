/*
 * Unit test for the L3TRYNEXTDEST route wraparound logic.
 *
 * In L3Code.c (lines 1458-1461) the routing failover increments
 * DEST_ROUTE and wraps from route 7 back to 1 (there are 6 route
 * slots, numbered 1-6; slot 0 means "no route").  A bug that used
 * assignment (=) instead of comparison (==) caused the wrap to fire
 * on every call, locking the route to slot 1.
 *
 * This test exercises the corrected logic in isolation.
 */

#include <stdio.h>
#include <string.h>

/* ---- Minimal type / struct definitions matching asmstrucs.h ---- */

typedef unsigned char  UCHAR;
typedef unsigned short USHORT;

struct ROUTE;  /* opaque; not dereferenced in this test */

typedef struct NR_DEST_ROUTE_ENTRY
{
    struct ROUTE *ROUT_NEIGHBOUR;
    UCHAR         ROUT_QUALITY;
    UCHAR         ROUT_OBSCOUNT;
    UCHAR         ROUT_LOCKED;
} *PNR_DEST_ROUTE_ENTRY;

typedef struct INP3_DEST_ROUTE_ENTRY
{
    struct ROUTE *ROUT_NEIGHBOUR;
    USHORT        STT;
    UCHAR         Hops;
} *PDEST_ROUTE_ENTRY;

typedef struct DEST_LIST
{
    struct DEST_LIST *DEST_CHAIN;

    UCHAR DEST_CALL[7];
    UCHAR DEST_ALIAS[6];

    UCHAR DEST_STATE;
    UCHAR DEST_LOCKED;

    UCHAR DEST_ROUTE;
    UCHAR INP3FLAGS;

    struct NR_DEST_ROUTE_ENTRY  NRROUTE[3];
    struct INP3_DEST_ROUTE_ENTRY INP3ROUTE[3];

    void *DEST_Q;

    int      DEST_RTT;
    int      DEST_COUNT;

    USHORT  *RouteLastTT;
} dest_list;

/* ---- Extracted wraparound logic (mirrors L3Code.c:1458-1461) ---- */

static void trynextdest_advance(struct DEST_LIST *DEST)
{
    DEST->DEST_ROUTE++;            /* to next */

    if (DEST->DEST_ROUTE == 7)
        DEST->DEST_ROUTE = 1;     /* wrap: try first route again */
}

/* ---- Test harness ------------------------------------------------ */

static int failures = 0;

static void check(const char *label, UCHAR before, UCHAR expected, UCHAR actual)
{
    if (actual == expected)
    {
        printf("PASS  %s: route %u -> %u\n", label, before, actual);
    }
    else
    {
        printf("FAIL  %s: route %u -> expected %u, got %u\n",
               label, before, expected, actual);
        failures++;
    }
}

int main(void)
{
    struct DEST_LIST dest;

    /* --- Test 1: route 1 -> 2 (simple advance) --- */
    memset(&dest, 0, sizeof(dest));
    dest.DEST_ROUTE = 1;
    trynextdest_advance(&dest);
    check("advance 1->2", 1, 2, dest.DEST_ROUTE);

    /* --- Test 2: route 5 -> 6 (advance near end) --- */
    memset(&dest, 0, sizeof(dest));
    dest.DEST_ROUTE = 5;
    trynextdest_advance(&dest);
    check("advance 5->6", 5, 6, dest.DEST_ROUTE);

    /* --- Test 3: route 6 -> 1 (wraparound) --- */
    memset(&dest, 0, sizeof(dest));
    dest.DEST_ROUTE = 6;
    trynextdest_advance(&dest);
    check("wraparound 6->1", 6, 1, dest.DEST_ROUTE);

    printf("\n%s\n", failures ? "SOME TESTS FAILED" : "ALL TESTS PASSED");
    return failures ? 1 : 0;
}
