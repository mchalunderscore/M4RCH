# Distinct native PWRGATE admission-drain C qualification

The new no-work source owner passes 85 actual C cases under ASan/UBSan. This is offline evidence for the bounded admission drain and retained once-only sequence. It does not identify the missing operand behind the actual d841 pre-request EBUSY refusal, and it does not establish a live PWRGATE request or teardown.

The selected source is `out/gfx-native-powergate-drain/prepared-owner-v2`. Its source receipt has SHA-256 `e55cf8f6bf8a5b8d979a567412cada0b1df38b5d7750183a34e448a38d9c39c1`. The actual C qualification `out/gfx-native-powergate-drain/owner-qualification-final-v2.json` has SHA-256 `041aed9b5ef9fc08bc9344477b835c56359133dcbaf5e79eb1ea40ff19c48e5f`.

Before any hardware read, the C owner consumes terminal intent, seals the owner and cancels the receive worker without blocking on its mutex. All hardware reads in the replay assert this durable intent, held PM reference and mutex. A repeated command cannot read hardware, write transport/CPU controls or delegate OFF.

The admission path logs CTRL44, STATUS48, RX114 and TX110 together, identifies the precise refusal condition, and preserves every removed raw mailbox message and metadata with that sample. Only EP32 with the exact word `0x0042000000000000` calls the unchanged receive service. Every preexisting EP0 frame, including an otherwise valid type7 ACK, seals the attempt before `202`; unexpected, invalid and crash frames likewise refuse. A fresh four-operand sample immediately before publication refuses newly returned RX, full TX, lost START or invalid register values.

The admission deadline is nominally 11ms using `jiffies` and `msecs_to_jiffies`; it is checked before and after finite receive-service calls. This does not impose a hard wall-clock upper bound. Independent hard limits allow 12 empty-RX/TX-wait polls and 64 removed admission frames. The 64th qualified frame seals, so at most 63 frames precede successful admission. Status samples are counted separately from TX-wait polls.

The replay covers an accepted EP32 notification and 63-frame drain, the 64-frame seal, every preexisting EP0 variant, wrong EP32 word and endpoint, invalid message/metadata/registers, crash and service/journal failures, frame/service deadlines, stalled-clock poll limit, TX readiness on the tenth retry and final-sample races. It also retains the original handshake/ACK, checked CPU RMW, paired OFF delegation, consumed retry, diagnostics and unknown startup tests. Post-request RX all-ones now refuses before removing a frame, and every removed post-request frame also records RX status.

The source preparation reads and verifies the frozen PWRGATE v5 sources without modifying them. Relative to the native STATUS baseline, the same four files change (`Makefile`, `asc-graph-init.c`, `gfx-reset-scope.h`, `recovery-cycle.h`) and one distinct header is added; the other 13 common C/header/Makefile sources are unchanged. The 69-page startup graph, 174 retained allocations and dormant render backing remain comparable. The old unused PWRGATE header and its source receipt are omitted only from the new copied owner; their provenance is bound as inputs.

The actual header replay mocks the existing receive/provider helpers. The unchanged receive source, original 55-case sanitizer qualification and native ranges are pinned separately. Nothing here proves live cessation, strict OFF, recovery, rendering, restart or DMA retirement. The new source has only `sample`, `gfx-snapshot` and one terminal `gfx-powergate`, with no work publication or release of retained backing.

Machine-readable source pins and cases are in [the evidence JSON](2026-10-09-gfx-native-powergate-drain-c-qualification.json).
