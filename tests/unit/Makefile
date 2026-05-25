CC      = gcc
CFLAGS  = -Wall -Werror

SRCS    = $(wildcard test_*.c)
TESTS   = $(SRCS:.c=)

all: $(TESTS)

test_%: test_%.c
	$(CC) $(CFLAGS) -o $@ $<

test: $(TESTS)
	@fail=0; \
	for t in $(TESTS); do \
		echo "=== Running $$t ==="; \
		./$$t || fail=1; \
	done; \
	exit $$fail

clean:
	rm -f $(TESTS)

.PHONY: all test clean
