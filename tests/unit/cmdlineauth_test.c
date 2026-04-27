#include "test_helpers.h"

#define main cmdlineauth_legacy_main
#include "../../CmdLineAuth.c"
#undef main

int main(void)
{
	assert_int_equal(51641, GetOneTimePasswordCode("secret", (time_t)1714212000),
		"OTP code should match the fixed regression vector");
	assert_int_equal(665155, GetOneTimePasswordCode("M0LTE", (time_t)1714212030),
		"OTP code should stay deterministic for a second fixed regression vector");
	assert_true(GetOneTimePasswordCode("secret", (time_t)1714212000) !=
		GetOneTimePasswordCode("secret", (time_t)1714212030),
		"OTP code should change when the 30-second time window changes");

	puts("cmdlineauth_test: PASS");
	return 0;
}
