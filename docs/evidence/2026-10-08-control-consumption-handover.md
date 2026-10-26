# first native control consumption; 32-refresh batch prepared

boot3cfad7b5-4782-4083-9043-8d15a295ff67, trial sourceae7476b and exact
slot22-startup-candidate artifacts. regular7.1.13-m4rch-gpu-contract kernel,
promoted package7.1.13-2 and default GRUB entry unchanged. all3 PD controllers
and USB role providers bound before/after; user confirms everything normal.

gate1 passes; gate2 returns0. the previous slot22 write-permission fault is
gone in this bounded observation. no EHLC crashlog header and zero mailbox
messages during30seconds. this is absence of a recorded fatal event, not a
proof that firmware remained healthy indefinitely.

native control12 cursors advance0/0/1 ->1/1/1. the unchanged opcode16 record
is consumed. this is our first native control-handler consumption on the
qualified mapping fixture, beyond earlier startup writes/faults. DATA globals
18eec8/146908/146914 finish zero, consistent with the refresh model. main
32c=1 and344=abcdabcd; prior header/power/status mutations remain present.
29 non-atomic owned-RAM snapshots have one unique hash and no observer errors;
consumption occurs before the first snapshot. no job/queue execution, receive
channel validation, complete initialization or GPU acceleration claim.

next candidate:32 identical operand-free opcode16 records, initial producer32.
only32 bytes differ from the successful fixture:31 additional opcode bytes and
the producer byte. same47 owned pages/100 device leaves/147 total mappings,
same36 writable device pages. no new permission, address, doorbell, FList,
shader or render/compute command. work0..11 stay empty RAM surrogates and
receive13..16 remain zero/unqualified. batch stays below the ring's page extent
and does not wrap. maximum32 explicitly checked, nonempty staging rejected.

15 mapping/serialization/batch-bound tests pass. offline matched-TEXT drain
replays1/2/16/32 records, returns with equal cursors and exact handler counts;
32-record replay7508 instructions. explicit zero private state, disabled cache
configuration and omitted pointer authentication remain model assumptions.
the drain's X0 is the producer snapshot, so32-record replay uses32, not1.
W=1 eight-helper build passes without warnings; all receipt hashes verified.
prepared artifacts:out/gpu-gravity-contract/refresh-batch-candidate.

private Apple AGX353.14/25G83 audit adds12 pinned instruction-site checks.
notifyFirmwareStarted sets CPU-object1715; bootFirmware waits for that bit
then sets CPU2a8; isGFXBooted reads1715. these are host bookkeeping, distinct
from our native control consumption. receivedMessageFromAKF dispatches masked
message class2 via an accelerator callback; callback routing remains unresolved.
initFirmwareSharedData maps CPU resource880 into main+200, currently zero in
our fixture. role/backing/extent are not qualified: do not fill this pointer
based only on its offset. five shared-pointer positions254..274 independently
corroborated. next audit: trace transport callbacks/start notification and the
complete resource880 allocation, then receive descriptors and nested contents.

evidence:2026-10-08-control-consumption-result.json,
2026-10-08-refresh-batch-{candidate,model}.json and
2026-10-08-private-startup-notification-audit.json. raw native capture:
asc-graph-init/boot-3cfad7b5-4782-4083-9043-8d15a295ff67.
analyze-control-result.py verifies the actual trial fixture before reporting
consumption. private binary/full disassembly/TEXT excluded from Git/bundle.
implementation-derived research, not clean-room.

NORMAL LINUX REBOOT required for the next publication. resources are pinned,
ASC stopped; AP_QUIESCED/IOP_SLEEP acknowledgements absent. never force-unload
or republish on this boot. no macOS change needed and no automatic reboot.
after r verify fresh boot, USB baseline and matching artifacts; run:

    sudo -n python experiments/t6040-gpu/run-root-envelope.py out/gpu-gravity-contract --graph --run

expected next result:control cursors32/32/32 with no fatal notification; any
partial drain or crash must be recorded. analyze against refresh-batch-candidate,
not the previous one-record fixture. rebuild using --control-refresh
--control-refresh-count 32. keep bounded mailbox/live
RAM captures. rendering still requires real channel state, job/command ABI,
allocation/coherency and interrupt completion, beyond this control batch.
