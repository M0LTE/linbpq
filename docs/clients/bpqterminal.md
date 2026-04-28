# BPQTerminal

`BPQTerminal.exe` is the Windows desktop terminal client that
ships with the BPQ32 installer.  It speaks to the local node
process directly (in-process via the BPQ32 DLL) rather than
over telnet, which gives it a richer view than a TCP terminal:

- A **monitor window** showing decoded frames sent and received,
  including supervisory frames.
- An **output window** showing responses to commands you've
  issued — supports normal Windows clipboard copy/paste.
- An **input window** for typing commands.

## Platform

**Windows-only.**  BPQTerminal is part of the Windows BPQ32
installer; there is no Linux build.  On Linux, use any
TCP-terminal client (`telnet`, `nc`, `screen //net…`,
[Pat winlink-go's terminal mode][pat], or the BPQ web admin)
against the configured `TCPPORT=` of the Telnet driver.

[pat]: https://getpat.io/

## Invocation

The binary takes a window-config index as its only argument:

```
BPQTerminal.exe 2
```

Multiple indices = multiple parallel windows with independently-
saved geometry, monitor toggles, and font choices.  Sizes /
positions / preferences are persisted on close.

## When you'd use it

- You're on Windows and want a monitor view next to the
  command prompt.
- You're investigating what's actually happening on a port and
  the BPQ web monitor isn't enough.
- You're using BPQ32 from a single-machine setup and don't
  want telnet involved.

For everything else — remote operation, multi-user setups,
mobile clients — telnet (LinBPQ's `TCPPORT=`) is the better
fit.  `BPQTermTCP.exe` is the Windows TCP-terminal sister
program but it's covered by any modern terminal app on either
OS.
