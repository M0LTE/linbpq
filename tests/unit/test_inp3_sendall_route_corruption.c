/*
 * test_inp3_sendall_route_corruption.c
 *
 * Verify that the Route pointer in sendAlltoOneNeigbour is NOT
 * incremented when a destination matches the neighbour's own call.
 *
 * The bug (BPQINP3.c ~line 1800): Route++ inside the self-referential
 * skip block corrupts the Route pointer for all subsequent iterations.
 * The continue already advances to the next Dest; Route must stay fixed.
 */

#include <stdio.h>
#include <string.h>
#include <stdlib.h>

/* ---- minimal struct stand-ins ---- */

struct ROUTE {
    char NEIGHBOUR_CALL[7];
    int  tag;                   /* identity marker for verification */
};

struct DEST_LIST {
    char DEST_CALL[7];
};

/* ---- helpers ---- */

static int failures = 0;

static void check(int cond, const char *msg)
{
    if (!cond) {
        fprintf(stderr, "FAIL: %s\n", msg);
        failures++;
    } else {
        fprintf(stdout, "PASS: %s\n", msg);
    }
}

/* ---- simulate the FIXED loop logic ---- */

/*
 * In the real code the loop is:
 *
 *   for (i = 0; i < MAXDESTS; i++) {
 *       Dest++;
 *       ...
 *       if (memcmp(Route->NEIGHBOUR_CALL, Dest->DEST_CALL, 7) == 0) {
 *           // BUGGY:  Route++;   <-- removed in the fix
 *           continue;
 *       }
 *       // ... use Route ...
 *   }
 *
 * We replicate just enough to prove Route stability.
 */

static int processed_count;   /* how many non-skipped dests we "sent to" */

static void simulate_fixed(struct ROUTE *Route,
                           struct DEST_LIST dests[], int ndests)
{
    int i;
    struct DEST_LIST *Dest = &dests[-1]; /* mirrors Dest-- before loop */

    processed_count = 0;

    for (i = 0; i < ndests; i++) {
        Dest++;

        if (memcmp(Route->NEIGHBOUR_CALL, Dest->DEST_CALL, 7) == 0) {
            /* Fixed version: no Route++ here, just skip */
            continue;
        }

        /* "process" this dest with Route */
        processed_count++;
    }
}

static void simulate_buggy(struct ROUTE *Route,
                           struct DEST_LIST dests[], int ndests)
{
    int i;
    struct DEST_LIST *Dest = &dests[-1];

    processed_count = 0;

    for (i = 0; i < ndests; i++) {
        Dest++;

        if (memcmp(Route->NEIGHBOUR_CALL, Dest->DEST_CALL, 7) == 0) {
            Route++;          /* BUG: corrupts Route */
            continue;
        }

        processed_count++;
    }
}

/* ---- main ---- */

int main(void)
{
    /*
     * Set up two contiguous ROUTE entries so Route++ has somewhere to go.
     * Route A (tag=1) is the intended parameter.
     * Route B (tag=2) sits right after it in memory.
     */
    struct ROUTE routes[2];
    memset(routes, 0, sizeof(routes));

    memcpy(routes[0].NEIGHBOUR_CALL, "CALL-A", 7);
    routes[0].tag = 1;

    memcpy(routes[1].NEIGHBOUR_CALL, "CALL-B", 7);
    routes[1].tag = 2;

    /*
     * Three destinations:
     *   dest[0] matches Route A's call  -> should be skipped
     *   dest[1] does not match           -> should be processed
     *   dest[2] does not match           -> should be processed
     */
    struct DEST_LIST dests[3];
    memset(dests, 0, sizeof(dests));

    memcpy(dests[0].DEST_CALL, "CALL-A", 7);   /* matches Route A */
    memcpy(dests[1].DEST_CALL, "OTHERC", 7);   /* no match         */
    memcpy(dests[2].DEST_CALL, "OTHERD", 7);   /* no match         */

    /* --- test the FIXED logic --- */

    struct ROUTE *routePtr = &routes[0];
    simulate_fixed(routePtr, dests, 3);

    check(routePtr->tag == 1,
          "Fixed: Route pointer still points to route A after skip");
    check(processed_count == 2,
          "Fixed: exactly 2 non-matching dests were processed");

    /* --- demonstrate the BUGGY logic corrupts Route --- */

    routePtr = &routes[0];
    simulate_buggy(routePtr, dests, 3);

    /*
     * After the buggy loop, routePtr itself is unchanged (C passes
     * pointers by value), but inside the loop the local copy was
     * incremented.  We verify the buggy version still processes 2 dests
     * (it does, because Route++ doesn't affect the skip/continue flow
     * for *Dest*), BUT the Route used for processing is wrong.
     *
     * To capture this we run a variant that records which tag was seen.
     */

    /* --- detailed tag-tracking variant --- */

    {
        int tags_seen_fixed[3]  = {0, 0, 0};
        int tags_seen_buggy[3]  = {0, 0, 0};
        int idx;
        struct ROUTE *R;
        struct DEST_LIST *D;

        /* Fixed */
        R = &routes[0];
        D = &dests[-1];
        idx = 0;
        for (int i = 0; i < 3; i++) {
            D++;
            if (memcmp(R->NEIGHBOUR_CALL, D->DEST_CALL, 7) == 0)
                continue;
            tags_seen_fixed[idx++] = R->tag;
        }

        check(tags_seen_fixed[0] == 1 && tags_seen_fixed[1] == 1,
              "Fixed: all processed dests used Route A (tag 1)");

        /* Buggy */
        R = &routes[0];
        D = &dests[-1];
        idx = 0;
        for (int i = 0; i < 3; i++) {
            D++;
            if (memcmp(R->NEIGHBOUR_CALL, D->DEST_CALL, 7) == 0) {
                R++;
                continue;
            }
            tags_seen_buggy[idx++] = R->tag;
        }

        check(tags_seen_buggy[0] == 2,
              "Buggy: first processed dest saw Route B (tag 2) -- corruption");
        check(tags_seen_buggy[0] != tags_seen_fixed[0],
              "Buggy and Fixed produce different Route tags (confirms bug)");
    }

    /* --- final verdict --- */

    if (failures) {
        fprintf(stderr, "\n%d test(s) FAILED\n", failures);
        return 1;
    }

    printf("\nAll tests passed.\n");
    return 0;
}
