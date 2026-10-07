# Pending control exposes primary startup fault; five-page batch prepared

Boot52a53fed-81d3-4131-9323-50b857301f47, source01534c9. Gate1 shadowwalk
passed; gate2 returned0 and Linux remained usable. All three USB role providers
and all three SPMI PD controllers bound before GPU; user says Everything normal
afterward. Kernel7.1.13-m4rch-gpu-contract, promoted package7.1.13-2 and GRUB
default1 unchanged; USBR001 backupentry3 remains. No macOS required.

One pending control16 changes startup behavior: new2576-byte/footer-valid
EHLC/Crg8 crashlog, one postpublication EP1 fatal notification. PC8050,
FARfffffc200021ca20, ESR9600004f: STRX22,[X8,X9], X8fffffc2000200000,
X91ca20, X220. Physical28801ca20 lies on prior read-only primarypage28801c000.
The control read/prefetch/write remain[0,0,1]: NOT consumed. Power changes differ
from empty fixture, consistent with extra startup activity, not completion.
30 live frames are identical after initial changes. No render/queue/full init
claim. Native input/USB/network unaffected by reported firmware panic.

BROADER NEXT BATCH: a bounded matched-TEXT continuation from8050 to8fb0
before the next table loop executes290 instructions and37 modeled primary
register writes, spanning seven pages. Two pages alreadyRW, five now newlyRW:
288008000,28800c000,288014000,288018000,28801c000. These include direct
programming and helper29610/29804 register accesses. The model uses explicit
ZERO private DATA and register RAM, native Crg8 registers, cached primary and
main pointers seeded; diagnostic logger33de8 substituted and authentication
omitted. It is instruction/address evidence, not hardware emulation or proof
of native sequence completion. Unknown code/memory abort; boundary explicit.
Do not describe this as an entire wake-function emulation; remaining table
loop and later branches/helpers are not covered by this continuation.

Same100 device leaves/47 owned pages/147total, now34 devicepagesRW rather
than29. No new address mapping. Graph bytes byte-identical to current trial:
one initial opcode16,producer1; twelve work channels remain empty RAM surrogates;
receive13..16 still unqualified. No extra doorbell, FList or GPU job. This batch
removes all identified page-permission barriers in the modeled startup segment
together instead of iterating each fault one at a time. Complete register
semantics remain experimental; evidence implementation-derived, not clean room.

12 mapping/serialization tests andW=1 eight-helper build pass without warnings.
Exact actual trial artifacts remainout/gpu-gravity-contract/control-refresh-candidate;
nextout/gpu-gravity-contract/primary-startup-candidate. Evidence:
 docs/evidence/2026-10-08-control-refresh-result.json
 docs/evidence/2026-10-08-control-refresh-crash.json
 docs/evidence/2026-10-08-primary-startup-model.json
 docs/evidence/2026-10-08-primary-startup-candidate.json
Raw capture asc-graph-init/boot-52a53fed-81d3-4131-9323-50b857301f47.

NORMAL LINUX REBOOT needed before next publication: current backing pinned;
never force unload or warm-start again. Fresh boot/USB/module receipt/TEXT
checks then sudo -n python experiments/t6040-gpu/run-root-envelope.py out/gpu-gravity-contract --graph --run
Keep30sec observation and live snapshots. Inspect fatal record, controlconsumer,
new object changes and input/USB. If further fault, audit whole next segment
and batch qualified grants before another reboot. Reproduction build needs
build-root-envelope.py out/gpu-gravity-contract --control-refresh.

---

