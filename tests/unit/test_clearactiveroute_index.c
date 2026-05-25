/*
 * Unit test for CLEARACTIVEROUTE array index dispatch.
 *
 * DEST_ROUTE 1-3  → NRROUTE[DEST_ROUTE - 1]
 * DEST_ROUTE 4-6  → INP3ROUTE[DEST_ROUTE - 4]
 * DEST_ROUTE 0    → no active route
 */

#include <stdio.h>
#include <string.h>

/* ---- minimal struct stubs matching asmstrucs.h layout ---- */

struct ROUTE
{
	char name[16];		/* identification only */
};

struct NR_DEST_ROUTE_ENTRY
{
	struct ROUTE *ROUT_NEIGHBOUR;
};

struct INP3_DEST_ROUTE_ENTRY
{
	struct ROUTE *ROUT_NEIGHBOUR;
};

struct DEST_LIST
{
	unsigned char DEST_ROUTE;
	struct NR_DEST_ROUTE_ENTRY   NRROUTE[3];
	struct INP3_DEST_ROUTE_ENTRY INP3ROUTE[3];
};

/* ---- function-under-test: fixed dispatch logic ---- */

static int check_active_route(struct DEST_LIST *DEST, struct ROUTE *ROUTE)
{
	if (DEST->DEST_ROUTE >= 1 && DEST->DEST_ROUTE <= 3
		? DEST->NRROUTE[DEST->DEST_ROUTE - 1].ROUT_NEIGHBOUR == ROUTE
		: (DEST->DEST_ROUTE >= 4 && DEST->DEST_ROUTE <= 6
			&& DEST->INP3ROUTE[DEST->DEST_ROUTE - 4].ROUT_NEIGHBOUR == ROUTE))
		return 1;

	return 0;
}

/* ---- helpers ---- */

static int failures = 0;

static void assert_match(int test, int expected, int actual, const char *desc)
{
	if (expected != actual)
	{
		fprintf(stderr, "FAIL test %d: %s (expected %d, got %d)\n",
			test, desc, expected, actual);
		failures++;
	}
	else
	{
		printf("PASS test %d: %s\n", test, desc);
	}
}

/* ---- main ---- */

int main(void)
{
	struct ROUTE routeA, routeB;
	struct DEST_LIST dest;

	memset(&routeA, 0, sizeof(routeA));
	memset(&routeB, 0, sizeof(routeB));
	snprintf(routeA.name, sizeof(routeA.name), "routeA");
	snprintf(routeB.name, sizeof(routeB.name), "routeB");

	/* Test 1: DEST_ROUTE=1, routeA in NRROUTE[0] → match */
	memset(&dest, 0, sizeof(dest));
	dest.DEST_ROUTE = 1;
	dest.NRROUTE[0].ROUT_NEIGHBOUR = &routeA;
	assert_match(1, 1, check_active_route(&dest, &routeA),
		"DEST_ROUTE=1, routeA in NRROUTE[0] should match");

	/* Test 2: DEST_ROUTE=2, routeA in NRROUTE[1] → match */
	memset(&dest, 0, sizeof(dest));
	dest.DEST_ROUTE = 2;
	dest.NRROUTE[1].ROUT_NEIGHBOUR = &routeA;
	assert_match(2, 1, check_active_route(&dest, &routeA),
		"DEST_ROUTE=2, routeA in NRROUTE[1] should match");

	/* Test 3: DEST_ROUTE=4, routeA in INP3ROUTE[0] → match */
	memset(&dest, 0, sizeof(dest));
	dest.DEST_ROUTE = 4;
	dest.INP3ROUTE[0].ROUT_NEIGHBOUR = &routeA;
	assert_match(3, 1, check_active_route(&dest, &routeA),
		"DEST_ROUTE=4, routeA in INP3ROUTE[0] should match");

	/* Test 4: DEST_ROUTE=5, routeA in INP3ROUTE[1] → match */
	memset(&dest, 0, sizeof(dest));
	dest.DEST_ROUTE = 5;
	dest.INP3ROUTE[1].ROUT_NEIGHBOUR = &routeA;
	assert_match(4, 1, check_active_route(&dest, &routeA),
		"DEST_ROUTE=5, routeA in INP3ROUTE[1] should match");

	/* Test 5: DEST_ROUTE=1, routeA NOT in NRROUTE[0] → no match */
	memset(&dest, 0, sizeof(dest));
	dest.DEST_ROUTE = 1;
	dest.NRROUTE[0].ROUT_NEIGHBOUR = &routeB;
	assert_match(5, 0, check_active_route(&dest, &routeA),
		"DEST_ROUTE=1, routeA NOT in NRROUTE[0] should not match");

	/* Test 6: DEST_ROUTE=0 → no active route, no match */
	memset(&dest, 0, sizeof(dest));
	dest.DEST_ROUTE = 0;
	assert_match(6, 0, check_active_route(&dest, &routeA),
		"DEST_ROUTE=0 should not match (no active route)");

	if (failures)
	{
		fprintf(stderr, "\n%d test(s) FAILED\n", failures);
		return 1;
	}

	printf("\nAll tests passed.\n");
	return 0;
}
