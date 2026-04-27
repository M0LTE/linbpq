#include "test_helpers.h"

#define qsort(base, nmemb, size, compar) ((void)0)
#define main nodemaptest_legacy_main
#include "../../NodeMapTest.c"
#undef main
#undef qsort

static void reset_node_state(void)
{
	free(Nodes);
	free(NodeLinks);
	Nodes = NULL;
	NodeLinks = NULL;
	NumberOfNodes = 0;
	NumberOfNodeLinks = 0;
}

int main(void)
{
	double lat = 0.0;
	double lon = 0.0;
	char buffer[] = "CALL1,CALL2,CALL3";
	char valid_locator[] = "IO91WM";
	char invalid_locator[] = "ZZ99ZZ";
	char * next;
	struct NodeData * first;
	struct NodeData * second;
	struct NodeLink * link;

	assert_int_equal(1, FromLOC(valid_locator, &lat, &lon),
		"FromLOC should accept a valid Maidenhead locator");
	assert_double_close(51.5, lat, 0.0001,
		"FromLOC should decode latitude");
	assert_double_close(-0.1666666667, lon, 0.0001,
		"FromLOC should decode longitude");
	assert_int_equal(0, FromLOC(invalid_locator, &lat, &lon),
		"FromLOC should reject invalid locators");

	next = strlop(buffer, ',');
	assert_string_equal("CALL1", buffer,
		"strlop should terminate the source buffer at the delimiter");
	assert_string_equal("CALL2,CALL3", next,
		"strlop should return the remainder of the string");
	assert_true(strlop(buffer, '|') == NULL,
		"strlop should return NULL when the delimiter is absent");
	assert_true(strlop(NULL, ',') == NULL,
		"strlop should protect against NULL input");

	reset_node_state();

	first = FindNode("G8BPQ-7");
	second = FindNode("G8BPQ-7");
	assert_true(first == second,
		"FindNode should reuse an existing node for the same call");
	assert_int_equal(1, NumberOfNodes,
		"FindNode should only create one node for duplicate lookups");
	assert_string_equal("G8BPQ-7", first->Comment,
		"FindNode should initialize the default comment from the call");

	link = FindLink("G8BPQ-7", "M0LTE-1", 2);
	assert_int_equal(2, NumberOfNodes,
		"FindLink should create missing endpoint nodes");
	assert_int_equal(1, NumberOfNodeLinks,
		"FindLink should create a single link record");
	assert_true(link == FindLink("M0LTE-1", "G8BPQ-7", 2),
		"FindLink should treat reversed endpoints as the same link");
	assert_int_equal(1, NumberOfNodeLinks,
		"FindLink should not duplicate reversed links");
	assert_true(link->Call1 != NULL && link->Call2 != NULL,
		"FindLink should attach both endpoint nodes");

	reset_node_state();

	puts("nodemaptest_test: PASS");
	return 0;
}
