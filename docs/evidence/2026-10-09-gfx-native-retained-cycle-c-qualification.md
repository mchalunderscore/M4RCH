# Native-ordered retained-cycle C qualification

The distinct native-ordered retained-cycle source passes 115 actual C cases
under ASan/UBSan. It recognizes fresh known status6a or6c after its own qualified
PWRGATE and strict physical OFF, performs the separate second paired ON, then
refreshes the native START admission. This addresses the exact pre-ON status6c
refusal observed on boot5bf0. No reentry, second physical OFF, application
recovery, triangle or DMA retirement has been established by this offline work.

Selected source is `out/gfx-native-retained-cycle/prepared-owner-v1`; its source
receipt has SHA-256
`59ca87b903980cac6dc9c5ea4fa44d4a346f1f9737a083eff7c50d1b6b0a7b44`.
Final actual C qualification
`out/gfx-native-retained-cycle/owner-qualification-final-v1.json` has SHA-256
`3db52593e9929d6cecb63602aa9d70dcaa3e77ef9576824617946e295fa2c2d0`.
The original frozen retained v6 owner, previous prepared source and historical
receipts remain unchanged.

The source delta is bounded. Three common files change: the Makefile selects
the distinct native macro, recovery-cycle includes the new header, and the
translation unit publishes the distinct ready marker and description. The new
core replaces only the copied retained-cycle header. The first successful drain
header and second coordinator header remain byte-identical. The selected
candidate still has 20 C/header/Makefile sources and the same 174 allocations,
installed host root, joined context and dormant render backing.

The typed command is `gfx-native-retained-cycle`. It preserves the first
request/ACK/CPU-stop/coordinator/OFF/PM-put fields and the entire first session.
It requires a fresh strict OFF witness and unchanged retained identities before
its one second PM get. After fresh ACTIVE accounting, all four ASC/FIFO operands
must be valid, with START clear, empty RX, available TX and known6a or6c. The
separate paired ON follows, then the same four operands are sampled again. A
third four-operand sample occurs after START-intent logging, immediately before
the final fresh CTRL44 RMW and sole START. Status6e,48,6d,0 and invalid values
refuse; no idle requirement is relaxed for the later native CPU-stop path.

The inspected native common start and V6 run bodies do not impose exact6a;
they motivate this explicit bounded hypothesis after the now captured
PWRGATE/strictOFF boundary. The source still seeks only autonomous HELLO12 and
the exact saved two endpoint maps. One separately owned request202, qualified
ACK, checked CPU-stop sequence, paired OFF and PM put can follow. No INIT220,
application start/root publication, context reattach, queue or counter reset,
firmware DATA restore, allocation release or general restart API is added.
Application rejoin remains a separate missing contract.

The kernel log truncation found in the v6 live capture is addressed directly:
each state observation now emits five complete newline rows with a shared
phase. The primary row contains result/refusal/intent/completion; companion
state, transport, management and OFF rows contain their respective operands.
Actual C formatting with worst-case integer widths and the longest operational
phase produced a maximum new row of 422 bytes, including its newline, below
the enforced 512-byte bound. Refusal and current second-state fields therefore
do not depend on a 1300-byte continuation. Frozen first-epoch and coordinator
records retain their original format and remain explicitly historical when
interpreting current second power ownership.

The actual-header replay covers successful known6c admission before and after
second ON; pre-ON refusal of unsupported status values; fresh post-ON and
immediate-START STATUS/RX/TX/control faults; and complete bounded log rows.
It retains the previous negative PM/reference/identity/first-history,
coordinator, transport/map/ACK, CPU stop and strict-OFF cases. Fresh post-ON and
immediate faults explicitly prove no START, management request or PM put occurs.
Consumed retries cannot perform another get, START, request or put. The actual
transformed receive worker refuses receive/scheduling after the distinct intent
without repairing an unqualified first-history flag.

The replay compiles the actual new header, the unchanged second coordinator
header and coordinate core, and the actual copied receive worker. First
successful OFF is simulated in this harness; the frozen 85-case drain proof and
the saved actual first OFF results compose separately. Provider, runtime PM,
mailbox/CPU, retained memory and MMIO bindings use RAM callbacks. This C
qualification performed no kernel build or load. The separate wrapper,
compiled-owner receipt and fresh-boot qualification must be bound before the
new hardware experiment.

Machine-readable source pins and cases are in [the evidence JSON](2026-10-09-gfx-native-retained-cycle-c-qualification.json).
