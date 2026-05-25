/*
 * test_inp3_routelasttt_index.c
 *
 * Verify that RouteLastTT is indexed by the TARGET neighbour's recNum
 * (the neighbour we are sending TO), not the source neighbour's recNum
 * (the neighbour we learned the route from).
 *
 * Bug: sendAlltoOneNeigbour and SendRIFToNewNeighbour used
 *      Entry->ROUT_NEIGHBOUR->recNum (source) instead of Route->recNum (target).
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

#define MAX_NEIGHBOURS 8

/* Minimal stand-in for a ROUTE / neighbour record */
struct ROUTE {
    int recNum;
    char name[16];
    int RTTIncrement;
    int RemoteMAXHOPS;
    int RemoteMAXRTT;
};

/* Minimal stand-in for an INP3 destination route entry */
struct INP3_DEST_ROUTE_ENTRY {
    struct ROUTE *ROUT_NEIGHBOUR;   /* neighbour we learned this route from */
    int STT;                        /* smoothed travel time */
    int Hops;
};

/* Minimal stand-in for DEST_LIST */
struct DEST_LIST {
    uint16_t RouteLastTT[MAX_NEIGHBOURS];
    struct INP3_DEST_ROUTE_ENTRY INP3ROUTE[1];
};

static int failures = 0;

static void check(int cond, const char *msg)
{
    if (!cond) {
        fprintf(stderr, "FAIL: %s\n", msg);
        failures++;
    } else {
        printf("PASS: %s\n", msg);
    }
}

/*
 * Simulate the FIXED sendAlltoOneNeigbour logic (lines 1804-1808).
 *
 * Route  = the neighbour we are sending TO (target).
 * Entry  = the best route entry for this destination (learned from
 *          Entry->ROUT_NEIGHBOUR, which is the source neighbour).
 *
 * The correct code indexes RouteLastTT by Route->recNum (target).
 */
static void sim_sendAlltoOneNeigbour_fixed(struct DEST_LIST *Dest,
                                           struct ROUTE *Route,
                                           struct INP3_DEST_ROUTE_ENTRY *Entry)
{
    int sendTT, lastTT;

    sendTT = Entry->STT + Entry->ROUT_NEIGHBOUR->RTTIncrement;

    /* FIXED: use Route->recNum (target), not Entry->ROUT_NEIGHBOUR->recNum */
    lastTT = Dest->RouteLastTT[Route->recNum];
    (void)lastTT;  /* would be used for threshold checks */

    Dest->RouteLastTT[Route->recNum] = sendTT;
}

/*
 * Simulate the BUGGY sendAlltoOneNeigbour logic for comparison.
 */
static void sim_sendAlltoOneNeigbour_buggy(struct DEST_LIST *Dest,
                                           struct ROUTE *Route,
                                           struct INP3_DEST_ROUTE_ENTRY *Entry)
{
    int sendTT, lastTT;

    sendTT = Entry->STT + Entry->ROUT_NEIGHBOUR->RTTIncrement;

    /* BUG: uses source neighbour index instead of target */
    lastTT = Dest->RouteLastTT[Entry->ROUT_NEIGHBOUR->recNum];
    (void)lastTT;

    Dest->RouteLastTT[Entry->ROUT_NEIGHBOUR->recNum] = sendTT;
}

/*
 * Simulate the FIXED SendRIFToNewNeighbour logic (line 1547).
 */
static void sim_SendRIFToNewNeighbour_fixed(struct DEST_LIST *Dest,
                                            struct ROUTE *Route,
                                            struct INP3_DEST_ROUTE_ENTRY *Entry)
{
    int sendTT;

    sendTT = Entry->STT + Entry->ROUT_NEIGHBOUR->RTTIncrement;

    /* FIXED: use Route->recNum (target) */
    Dest->RouteLastTT[Route->recNum] = sendTT;
}

/*
 * Simulate the BUGGY SendRIFToNewNeighbour logic for comparison.
 */
static void sim_SendRIFToNewNeighbour_buggy(struct DEST_LIST *Dest,
                                            struct ROUTE *Route,
                                            struct INP3_DEST_ROUTE_ENTRY *Entry)
{
    int sendTT;

    sendTT = Entry->STT + Entry->ROUT_NEIGHBOUR->RTTIncrement;

    /* BUG: uses source neighbour index */
    Dest->RouteLastTT[Entry->ROUT_NEIGHBOUR->recNum] = sendTT;
}

int main(void)
{
    /* Three neighbours:
     *   A  recNum=0  -- source neighbour (we learned the route FROM A)
     *   B  recNum=1  -- target neighbour (we are sending TO B)
     *   C  recNum=2  -- another neighbour (bystander)
     */
    struct ROUTE routeA = { .recNum = 0, .name = "A-source",   .RTTIncrement = 10 };
    struct ROUTE routeB = { .recNum = 1, .name = "B-target",   .RTTIncrement = 20 };
    struct ROUTE routeC = { .recNum = 2, .name = "C-bystander",.RTTIncrement = 30 };
    (void)routeC;

    struct DEST_LIST dest;
    struct INP3_DEST_ROUTE_ENTRY entry;

    int expectedTT;

    /* ------------------------------------------------------------------
     * TEST 1: Fixed sendAlltoOneNeigbour writes to target index (B)
     * ------------------------------------------------------------------ */
    memset(&dest, 0, sizeof(dest));
    entry.ROUT_NEIGHBOUR = &routeA;     /* learned from A */
    entry.STT  = 100;
    entry.Hops = 2;

    expectedTT = entry.STT + routeA.RTTIncrement;  /* 100 + 10 = 110 */

    sim_sendAlltoOneNeigbour_fixed(&dest, &routeB, &entry);

    check(dest.RouteLastTT[routeB.recNum] == expectedTT,
          "sendAlltoOneNeigbour fixed: RouteLastTT[target B] updated");
    check(dest.RouteLastTT[routeA.recNum] == 0,
          "sendAlltoOneNeigbour fixed: RouteLastTT[source A] untouched");

    /* ------------------------------------------------------------------
     * TEST 2: Buggy sendAlltoOneNeigbour writes to WRONG index (A)
     * ------------------------------------------------------------------ */
    memset(&dest, 0, sizeof(dest));
    entry.ROUT_NEIGHBOUR = &routeA;
    entry.STT  = 100;
    entry.Hops = 2;

    sim_sendAlltoOneNeigbour_buggy(&dest, &routeB, &entry);

    check(dest.RouteLastTT[routeA.recNum] == expectedTT,
          "sendAlltoOneNeigbour buggy: RouteLastTT[source A] incorrectly updated");
    check(dest.RouteLastTT[routeB.recNum] == 0,
          "sendAlltoOneNeigbour buggy: RouteLastTT[target B] left at zero (bug)");

    /* ------------------------------------------------------------------
     * TEST 3: Fixed SendRIFToNewNeighbour writes to target index (B)
     * ------------------------------------------------------------------ */
    memset(&dest, 0, sizeof(dest));
    entry.ROUT_NEIGHBOUR = &routeA;
    entry.STT  = 200;
    entry.Hops = 3;

    expectedTT = entry.STT + routeA.RTTIncrement;  /* 200 + 10 = 210 */

    sim_SendRIFToNewNeighbour_fixed(&dest, &routeB, &entry);

    check(dest.RouteLastTT[routeB.recNum] == expectedTT,
          "SendRIFToNewNeighbour fixed: RouteLastTT[target B] updated");
    check(dest.RouteLastTT[routeA.recNum] == 0,
          "SendRIFToNewNeighbour fixed: RouteLastTT[source A] untouched");

    /* ------------------------------------------------------------------
     * TEST 4: Buggy SendRIFToNewNeighbour writes to WRONG index (A)
     * ------------------------------------------------------------------ */
    memset(&dest, 0, sizeof(dest));
    entry.ROUT_NEIGHBOUR = &routeA;
    entry.STT  = 200;
    entry.Hops = 3;

    sim_SendRIFToNewNeighbour_buggy(&dest, &routeB, &entry);

    check(dest.RouteLastTT[routeA.recNum] == expectedTT,
          "SendRIFToNewNeighbour buggy: RouteLastTT[source A] incorrectly updated");
    check(dest.RouteLastTT[routeB.recNum] == 0,
          "SendRIFToNewNeighbour buggy: RouteLastTT[target B] left at zero (bug)");

    /* ------------------------------------------------------------------
     * TEST 5: Read path (lastTT) also uses target index in fixed version
     * ------------------------------------------------------------------ */
    memset(&dest, 0, sizeof(dest));
    dest.RouteLastTT[routeB.recNum] = 500;   /* previously sent TT to B */
    dest.RouteLastTT[routeA.recNum] = 999;   /* some unrelated value at A */

    entry.ROUT_NEIGHBOUR = &routeA;
    entry.STT  = 100;
    entry.Hops = 1;

    /* The fixed read path should retrieve index 1 (target B) = 500,
     * not index 0 (source A) = 999. After the call the value at B
     * should be overwritten with the new sendTT. */
    sim_sendAlltoOneNeigbour_fixed(&dest, &routeB, &entry);

    expectedTT = entry.STT + routeA.RTTIncrement;  /* 110 */

    check(dest.RouteLastTT[routeB.recNum] == expectedTT,
          "Read path: fixed code reads and then overwrites RouteLastTT[target B]");
    check(dest.RouteLastTT[routeA.recNum] == 999,
          "Read path: RouteLastTT[source A] remains untouched at 999");

    printf("\n%s\n", failures ? "SOME TESTS FAILED" : "ALL TESTS PASSED");
    return failures ? 1 : 0;
}
