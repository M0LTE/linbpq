CC ?= gcc
CFLAGS ?= -Wall -Wextra -std=gnu11 -g

TEST_BINS = unit/cmdlineauth_test unit/nodemaptest_test

.PHONY: all run clean

all: $(TEST_BINS)

run: all
	./unit/cmdlineauth_test
	./unit/nodemaptest_test

unit/cmdlineauth_test: unit/cmdlineauth_test.c
	$(CC) $(CFLAGS) -o $@ $<

unit/nodemaptest_test: unit/nodemaptest_test.c
	$(CC) $(CFLAGS) -o $@ $<

clean:
	rm -f $(TEST_BINS)
