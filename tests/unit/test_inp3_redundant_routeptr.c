/*
 * test_inp3_redundant_routeptr.c
 *
 * Verify that loop iteration using array indexing (&array[i]) produces
 * correct sequential access, demonstrating that an extra pointer increment
 * (ptr++) after the if-block is unnecessary when the pointer is reassigned
 * from the array at the top of each iteration.
 *
 * Bug: BPQINP3.c UpdateNode had a redundant ROUTEPTR++ at line 692 inside
 *      a for (i = 0; i < 3; i++) loop where ROUTEPTR is set to
 *      &Dest->INP3ROUTE[i] at the top of each iteration.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* Minimal stand-in for the real INP3_DEST_ROUTE_ENTRY */
struct INP3_DEST_ROUTE_ENTRY
{
    void *ROUT_NEIGHBOUR;
};

static int test_array_index_finds_null_slot(void)
{
    /*
     * Set up 3 route entries: [occupied, NULL, occupied]
     * The loop should find the NULL entry at index 1.
     */
    struct INP3_DEST_ROUTE_ENTRY routes[3];
    static int dummy_neighbour_a;
    static int dummy_neighbour_b;

    routes[0].ROUT_NEIGHBOUR = &dummy_neighbour_a;  /* occupied */
    routes[1].ROUT_NEIGHBOUR = NULL;                 /* free slot */
    routes[2].ROUT_NEIGHBOUR = &dummy_neighbour_b;  /* occupied */

    int found_index = -1;
    int i;
    struct INP3_DEST_ROUTE_ENTRY *ROUTEPTR;

    for (i = 0; i < 3; i++)
    {
        ROUTEPTR = &routes[i];

        if (ROUTEPTR->ROUT_NEIGHBOUR == NULL)
        {
            found_index = i;
            break;
        }
        /* No ROUTEPTR++ here -- the reassignment at loop top handles it */
    }

    if (found_index != 1)
    {
        fprintf(stderr, "FAIL: expected NULL slot at index 1, got %d\n",
                found_index);
        return 1;
    }

    printf("PASS: array indexing correctly found NULL slot at index 1\n");
    return 0;
}

static int test_redundant_increment_has_no_effect(void)
{
    /*
     * Show that adding ptr++ after the if-block doesn't change the result,
     * because ptr is reassigned from &array[i] at the start of each
     * iteration.  Both loops (with and without the extra increment) must
     * visit exactly the same elements in the same order.
     */
    struct INP3_DEST_ROUTE_ENTRY routes[3];
    static int dummy_neighbour_a;
    static int dummy_neighbour_b;

    routes[0].ROUT_NEIGHBOUR = &dummy_neighbour_a;
    routes[1].ROUT_NEIGHBOUR = NULL;
    routes[2].ROUT_NEIGHBOUR = &dummy_neighbour_b;

    /* --- Loop WITHOUT redundant increment --- */
    int found_without = -1;
    {
        int i;
        struct INP3_DEST_ROUTE_ENTRY *ROUTEPTR;
        for (i = 0; i < 3; i++)
        {
            ROUTEPTR = &routes[i];
            if (ROUTEPTR->ROUT_NEIGHBOUR == NULL)
            {
                found_without = i;
                break;
            }
        }
    }

    /* --- Loop WITH redundant increment (mirrors the old buggy code) --- */
    int found_with = -1;
    {
        int i;
        struct INP3_DEST_ROUTE_ENTRY *ROUTEPTR;
        for (i = 0; i < 3; i++)
        {
            ROUTEPTR = &routes[i];
            if (ROUTEPTR->ROUT_NEIGHBOUR == NULL)
            {
                found_with = i;
                break;
            }
            ROUTEPTR++;  /* redundant -- overwritten at loop top */
        }
    }

    if (found_without != found_with)
    {
        fprintf(stderr,
                "FAIL: results differ -- without=%d, with=%d\n",
                found_without, found_with);
        return 1;
    }

    if (found_without != 1)
    {
        fprintf(stderr,
                "FAIL: expected both loops to find index 1, got %d\n",
                found_without);
        return 1;
    }

    printf("PASS: redundant ptr++ has no effect on iteration result "
           "(both found index %d)\n", found_without);
    return 0;
}

int main(void)
{
    int failures = 0;

    failures += test_array_index_finds_null_slot();
    failures += test_redundant_increment_has_no_effect();

    if (failures)
    {
        fprintf(stderr, "\n%d test(s) FAILED\n", failures);
        return 1;
    }

    printf("\nAll tests passed.\n");
    return 0;
}
