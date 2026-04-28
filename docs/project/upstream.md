# Upstream documentation

The authoritative documentation for BPQ32/LinBPQ is John
Wiseman G8BPQ's collection at
[www.cantab.net/users/john.wiseman/Documents][bpqdocs].
This page lists every document linked from the upstream index
and its rewrite status on this site.

This site is a re-presentation of John's work, organised by user
journey and fact-checked against the binary plus the integration
test suite.  All technical content is faithful to upstream;
where this site disagrees with upstream that's a bug here or a
behaviour change in the binary that needs an issue filed.

[bpqdocs]: https://www.cantab.net/users/john.wiseman/Documents/

## Status legend

- **Rewritten** — page has been converted to Markdown, fact-
  checked, and lives in this site's nav.
- **Partial** — some material is here but the rewrite isn't
  complete.
- **Pending** — not yet started; upstream link is the canonical
  source meanwhile.

## Index

### Installation and quickstart

| Upstream page | Status | This site |
|---------------|--------|-----------|
| [BPQ32 Installation][BPQ32-Installation] | Out of scope | Windows-only — this site documents LinBPQ |
| [BPQ Quickstart Guide (Ken KD6PGI)][Quickstart_Guide] | Out of scope | Windows-only walkthrough |
| [LinBPQ Installation][InstallingLINBPQ] | Rewritten | [Getting started](../getting-started/index.md) |

[BPQ32-Installation]: https://www.cantab.net/users/john.wiseman/Documents/BPQ32%20Installation.htm
[Quickstart_Guide]: https://www.cantab.net/users/john.wiseman/Documents/Quickstart_Guide.html
[InstallingLINBPQ]: https://www.cantab.net/users/john.wiseman/Documents/InstallingLINBPQ.html

### Configuration

| Upstream page | Status | This site |
|---------------|--------|-----------|
| [BPQ32 Configuration File Description][BPQCFGFile] | Rewritten | [Configuration reference](../configuration/reference.md) |
| [BPQ32 RS232 Cabling][rs232-cabling] | Out of scope | Hardware-specific RS232 cabling guide for now-uncommon HDLC cards; defer until someone needs it. |

[BPQCFGFile]: https://www.cantab.net/users/john.wiseman/Documents/BPQCFGFile.html
[rs232-cabling]: https://www.cantab.net/users/john.wiseman/Documents/BPQ32%20RS232%20Cabling.htm

### Subsystems

| Upstream page | Status | This site |
|---------------|--------|-----------|
| [BPQ Mail Server][MailServer] | Rewritten | [BBS / Mail](../subsystems/bbsmail.md) |
| [BPQ Mail Server Configuration][MailServerConfiguration] | Rewritten | [BBS / Mail](../subsystems/bbsmail.md) |
| [BPQ Mail Server Mail Forwarding][Forwarding] | Rewritten | [Inter-BBS forwarding](../subsystems/bbs-forwarding.md) |
| [BPQ Mail and Chat Hints and Kinks][HintsandKinks] | Rewritten | Folded into [BBS / Mail](../subsystems/bbsmail.md) "Hints and gotchas" |
| [Mail Forwarding to/from Winlink][RMSForwarding] | Rewritten | [Inter-BBS forwarding](../subsystems/bbs-forwarding.md) |
| [Winlink interworking changes][BBSAttachments] | Rewritten | [Inter-BBS forwarding](../subsystems/bbs-forwarding.md) (Attachments section) |
| [BPQ Mail Server email Client Configuration][eMailClientConfiguration] | Rewritten | [BBS email gateways](../subsystems/bbs-email.md) |
| [BPQ Mail Server email Gateway][ISPGateway] | Rewritten | [BBS email gateways](../subsystems/bbs-email.md) |
| [BPQ Mail Server Changelog][BBSChangeLog] | Out of scope | Upstream changelog; not re-presented here |
| [BBS User Commands][BBSUserCommands] | Rewritten | [BBS user commands](../subsystems/bbs-user-commands.md) |
| [APRS Digipeater/IGate][APRSDigiGate] | Pending | [APRS](../subsystems/aprs.md) |
| [APRS Mapping and Messaging Application][BPQAPRS] | Pending | — |
| [Guide to Chat Network Map System][BPQChatMap] | Pending | — |
| [IP Gateway Feature][IPGateway] | Rewritten | [IP gateway](../subsystems/ipgateway.md) |

[MailServer]: https://www.cantab.net/users/john.wiseman/Documents/MailServer.html
[MailServerConfiguration]: https://www.cantab.net/users/john.wiseman/Documents/MailServerConfiguration.html
[Forwarding]: https://www.cantab.net/users/john.wiseman/Documents/Forwarding.html
[HintsandKinks]: https://www.cantab.net/users/john.wiseman/Documents/HintsandKinks.html
[RMSForwarding]: https://www.cantab.net/users/john.wiseman/Documents/RMSForwarding.html
[BBSAttachments]: https://www.cantab.net/users/john.wiseman/Documents/BBSAttachments.html
[eMailClientConfiguration]: https://www.cantab.net/users/john.wiseman/Documents/eMailClientConfiguration.html
[ISPGateway]: https://www.cantab.net/users/john.wiseman/Documents/ISPGateway.html
[BBSChangeLog]: https://www.cantab.net/users/john.wiseman/Documents/BBSChangeLog.html
[BBSUserCommands]: https://www.cantab.net/users/john.wiseman/Documents/BBSUserCommands.html
[APRSDigiGate]: https://www.cantab.net/users/john.wiseman/Documents/APRSDigiGate.html
[BPQAPRS]: https://www.cantab.net/users/john.wiseman/Documents/BPQAPRS.htm
[BPQChatMap]: https://www.cantab.net/users/john.wiseman/Documents/BPQChatMap.htm
[IPGateway]: https://www.cantab.net/users/john.wiseman/Documents/IPGateway.html

### Protocols and interfaces

| Upstream page | Status | This site |
|---------------|--------|-----------|
| [BPQAXIP Configuration][BPQAXIPConfiguration] | Rewritten | [AX/IP over UDP](../protocols/axip.md) |
| [BPQtoAGW][BPQtoAGW] | Pending | — |
| [BPQ Host Mode Emulator][BPQHostModeEmulator] | Pending | — |
| [BPQ Ethernet][BPQEthernet] | Pending | — |
| [BPQ Virtual Serial Port Driver][VirtualSerial] | Pending | — |
| [Using Pactor with BPQ32][UsingPactor] | Pending | — |
| [Using WINMOR with BPQ32][UsingWINMOR] | Pending | — |
| [Airmail to WINMOR][AirmailtoWINMOR] | Pending | — |

[BPQAXIPConfiguration]: https://www.cantab.net/users/john.wiseman/Documents/BPQAXIP%20Configuration.htm
[BPQtoAGW]: https://www.cantab.net/users/john.wiseman/Documents/BPQtoAGW.htm
[BPQHostModeEmulator]: https://www.cantab.net/users/john.wiseman/Documents/BPQ%20Host%20Mode%20Emulator.htm
[BPQEthernet]: https://www.cantab.net/users/john.wiseman/Documents/BPQ%20Ethernet.htm
[VirtualSerial]: https://www.cantab.net/users/john.wiseman/Documents/G8BPQ%20Virtual%20Serial%20Port%20Driver.htm
[UsingPactor]: https://www.cantab.net/users/john.wiseman/Documents/Using%20Pactor.htm
[UsingWINMOR]: https://www.cantab.net/users/john.wiseman/Documents/Using%20WINMOR.htm
[AirmailtoWINMOR]: https://www.cantab.net/users/john.wiseman/Documents/AirmailtoWINMOR.htm

### Terminal applications

| Upstream page | Status | This site |
|---------------|--------|-----------|
| [BPQTerminal][BPQTerminal] | Pending | — |
| [BPQTermTCP][BPQTermTCP] | Pending | — |
| [BPQ OCX Programming][BPQOCX] | Pending | — |

[BPQTerminal]: https://www.cantab.net/users/john.wiseman/Documents/BPQTerminal.htm
[BPQTermTCP]: https://www.cantab.net/users/john.wiseman/Documents/BPQTermTCP.htm
[BPQOCX]: https://www.cantab.net/users/john.wiseman/Documents/BPQ%20OCX%20Programming.htm

### Changelogs

| Upstream page | Status | This site |
|---------------|--------|-----------|
| [BPQ32 Node Changelog][NodeChangeLog] | Pending | — |
| [Support Programs Changelog][SupportProgsChangeLog] | Pending | — |

[NodeChangeLog]: https://www.cantab.net/users/john.wiseman/Documents/NodeChangeLog.html
[SupportProgsChangeLog]: https://www.cantab.net/users/john.wiseman/Documents/SupportProgsChangeLog.html
