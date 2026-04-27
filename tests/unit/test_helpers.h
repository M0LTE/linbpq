#ifndef LINBPQ_TEST_HELPERS_H
#define LINBPQ_TEST_HELPERS_H

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void assert_true(int condition, const char * message)
{
	if (!condition)
	{
		fprintf(stderr, "FAIL: %s\n", message);
		exit(1);
	}
}

static void assert_int_equal(int expected, int actual, const char * message)
{
	if (expected != actual)
	{
		fprintf(stderr, "FAIL: %s (expected %d, got %d)\n", message, expected, actual);
		exit(1);
	}
}

static void assert_string_equal(const char * expected, const char * actual, const char * message)
{
	if (strcmp(expected, actual) != 0)
	{
		fprintf(stderr, "FAIL: %s (expected \"%s\", got \"%s\")\n", message, expected, actual);
		exit(1);
	}
}

static void assert_double_close(double expected, double actual, double tolerance, const char * message)
{
	if (fabs(expected - actual) > tolerance)
	{
		fprintf(stderr, "FAIL: %s (expected %.12f, got %.12f)\n", message, expected, actual);
		exit(1);
	}
}

#endif
