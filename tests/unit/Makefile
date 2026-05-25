CC      = gcc
CFLAGS  = -Wall -Werror

SRCS    = $(wildcard test_*.c)
TESTS   = $(SRCS:.c=)

all: $(TESTS)

test_%: test_%.c
	$(CC) $(CFLAGS) -o $@ $<

test: $(TESTS)
	@failed=0; \
	for t in $(TESTS); do \
		echo "--- Running $$t ---"; \
		./$$t || failed=$$((failed + 1)); \
	done; \
	if [ $$failed -ne 0 ]; then \
		echo "$$failed test suite(s) failed"; \
		exit 1; \
	fi; \
	echo "All test suites passed."

clean:
	rm -f $(TESTS)

.PHONY: all test clean
