CC      = gcc
CFLAGS  = -Wall -Werror

SRCS    = $(wildcard test_*.c)
TESTS   = $(SRCS:.c=)

.PHONY: test clean

test: $(TESTS)
	@for t in $(TESTS); do \
		echo "=== Running $$t ==="; \
		./$$t || exit 1; \
	done

test_%: test_%.c
	$(CC) $(CFLAGS) -o $@ $<

clean:
	rm -f $(TESTS)
