/*
 * Unit test for INP3 RTTIncrement calculation.
 *
 * RTTIncrement should be the average of our SRTT and the neighbour's SRTT
 * (see asmstrucs.h comment: "Average of Ours and Neighbours SRTT in 10 ms").
 * When NeighbourSRTT is not yet known (zero), fall back to SRTT / 2.
 */

#include <stdio.h>
#include <stdlib.h>

struct ROUTE
{
	int SRTT;
	int NeighbourSRTT;
	int RTTIncrement;
};

static void calculate_rttincrement(struct ROUTE *Route)
{
	if (Route->NeighbourSRTT)
		Route->RTTIncrement = (Route->SRTT + Route->NeighbourSRTT) / 2;
	else
		Route->RTTIncrement = Route->SRTT / 2;
}

static int check(const char *label, int srtt, int neighbour_srtt, int expected)
{
	struct ROUTE r = { .SRTT = srtt, .NeighbourSRTT = neighbour_srtt };

	calculate_rttincrement(&r);

	if (r.RTTIncrement != expected)
	{
		fprintf(stderr, "FAIL %s: SRTT=%d NeighbourSRTT=%d expected=%d got=%d\n",
			label, srtt, neighbour_srtt, expected, r.RTTIncrement);
		return 1;
	}

	printf("PASS %s\n", label);
	return 0;
}

int main(void)
{
	int failures = 0;

	/* NeighbourSRTT unknown: fall back to SRTT / 2 */
	failures += check("fallback_srtt_div2",       100, 0,   50);

	/* Normal case: average of SRTT and NeighbourSRTT */
	failures += check("average_different",         100, 200, 150);

	/* Equal values: average equals either value */
	failures += check("average_equal",             100, 100, 100);

	/* Minimum non-zero values */
	failures += check("minimum_nonzero",             1, 1,     1);

	/* Both zero */
	failures += check("both_zero",                   0, 0,     0);

	return failures ? 1 : 0;
}
