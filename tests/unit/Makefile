CC      = gcc
CFLAGS  = -Wall -Werror

SRCS    = $(wildcard test_*.c)
TESTS   = $(SRCS:.c=)

.PHONY: test clean

test: $(TESTS)
	@fail=0; \
	for t in $(TESTS); do \
<<<<<<< HEAD
		echo "--- running $$t ---"; \
=======
		echo "--- $$t ---"; \
>>>>>>> origin/fix/inp3-rttincrement-neighbour-srtt
		./$$t || fail=1; \
	done; \
	exit $$fail

test_%: test_%.c
	$(CC) $(CFLAGS) -o $@ $<

clean:
	rm -f $(TESTS)
