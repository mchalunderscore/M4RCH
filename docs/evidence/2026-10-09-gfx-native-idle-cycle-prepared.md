# Native idle-stage retained-cycle candidate

The distinct candidate at `out/gfx-native-idle-cycle/candidate` is built,
finalized and independently reviewed for one fresh-boot management experiment.
It has never been loaded. The [preceding actual trial](2026-10-09-gfx-native-retained-cycle-live-outcome.md)
repeated strict physical OFF, restored ACTIVE with one new PM reference and
completed a separate second paired ON. Its guard stopped at fresh post-ON
STATUS6d before START. Same-owner firmware restart remains untested.

| Final input | SHA256 |
| --- | --- |
| Owner module | `6c37c9f63419364fade9d1e402bce554b25c9cb5b855e514fb017de193d9f56b` |
| Build receipt | `027b5dbf79e2cceecdb82823c5daba4bc5b7cdacb05cb7228b2b11cb5d6deeea` |
| Preparation | `2a8cc03ff760702d2d052fc8f047527cafa54a252e25d67e2aef664036b31d80` |
| Source v1 receipt | `313135beb0a845b461f07398a56072937c8e89f3771f161a30b6c1f13aaa7d5d` |

The W1 build returned zero with no warnings and matches the installed
`7.1.13-m4rch-gpu-native-reset` kernel. Actual C ASan/UBSan replay passes135 cases,
including20 focused stage/ownership additions and the actual headers,
coordinator and receive worker. Python checks pass74 targeted cases, four
cold-main and ten resident-main flows intercepted in RAM. Unchanged v8 C115
and Python69 qualifications are composed. Complete log rows measure at most418
bytes under511. Final independent review binds167 inputs and all57 ELF imports.
Root checked ten artifacts, twenty sources, sixteen preparation inputs and all38
prepared-evidence pins. The nine non-owner artifacts and dormant graph/backing
remain byte-identical. No kernel rebuild or boot configuration change occurred.

The [bounded native finding](2026-10-09-gfx-native-retained-cycle-post-on-status6d-native-start.md)
shows that6d satisfies V6's selected idle predicate and that native options0
start/runCPU has no exact STATUS48 gate. This does not decode every upper status
bit or prove bootability. The new family keeps pre-ON admission at exact6a/6c.
Post-ON and subsequent fresh guards additionally permit exact6d only with its
own second ON attempted/completed, owned second PM reference, clean ACTIVE
accounting and preserved first-OFF/identity predicates. START must remain clear,
RX empty and TX valid/available. The four operands are refreshed after ON and
again after START-intent logging; the write uses one immediate fresh CTRL RMW
and requires a valid START-set readback. Premature6d, invalid ownership and
unknown statuses remain refused. START intent alone is not evidence of a write.

The frozen first drain/202/checkedstop/pairedOFF/PMput and shared worker remain
unchanged. Both durable intents and first coordinator history remain separate.
All174 page pointer/PA identities, root, context, consumer, mappings and exclusive
claims stay retained. One successful first-OFF raw capture and fresh kernel
gates are prerequisites for the one second intent. The only autonomous protocol
is HELLO12 and the exact final map ACK. If that succeeds, the bounded management
hypothesis permits one own second202/nativeACK/checkedCPUstop/separatepairedOFF/
one secondPMput/strictOFF. Unknown outcomes seal further controls and retain
resources without a compensating put.

No INIT220, app endpoint start, new root/context, DATA restore, queue reset,
work or release is introduced. Mapper runtime equivalence, application rejoin,
joined DMA retirement, GPU execution and rendered pixels remain unverified.
A transport or management success would establish only that limited scope.

Current boot `96264748-b049-403f-9240-975716f71d0c` retains the consumed v8 owner
and second reference held1/usage1/ACTIVE/error0. Both intents are sealed. Only
its existing typed diagnostics are admitted. The new preflight CLI actually
refused this boot before candidate/sysfs/native/GPU access and created no output;
the old v8 wrapper refused all four commands against the new receipt. This boot
and four older consumed boots are refused. A normal fresh user boot is required;
GRUB default5 and the installed kernel remain correct.

The [prepared JSON](2026-10-09-gfx-native-idle-cycle-prepared.json), SHA
`13bb08ca4633ff8b4562a6ba388b7f19d78da2b6b92c37d47af1d1fa82f0ca21`,
binds the exact final artifacts, qualification, independent reports and root
validation. Read `/boot/GPUC003/ASTRA-RESTART.md` for the canonical gated commands.
Root alone operates hardware; all subagent work was offline. No new owner
hardware trial has occurred.
