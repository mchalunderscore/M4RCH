# Notification binding target resolved — 2026-10-08

Executed the pinned AGX353.14 native notification binding slice and root pointer serialization slice in 512 randomized whole-memory comparisons. The actual slot2d8 identity converter executes for all three mapped addresses. External allocation and CPU/GPU alias correspondence remain supplied boundaries.

The previously qualified allocation descriptor pairs hostFW CPU field960 with mapped field970 and an extent of0xe440 (58,432 bytes). Native root serialization89cdb84..89cdbc8 converts field970 and stores it at root+b0. Therefore the notification binding target is the graph status_b object, not the main buffer. Its state and entry pointers are at status_b+48e0 and+48e8; native initialization clears state head0/tail10 and status_b+48f0(u64),+4900(u32),+4910(u32).

The current graph receipt reserves0x10000 bytes for status_b atfffffc2000140000, covering the allocation descriptor extent without extra pages. Its current input extent0xe43c is four bytes shorter than the native allocation descriptor; the reserved tail is zeroed. Notification fields live at firmware VAsfffffc20001448e0 andfffffc20001448e8. Existing main-buffer framework offsets are a different object and must not substitute for these.

Next: bind the owned notification pages through status_b, explicitly validate cold-zero versus post-init queued state, and walk both pointers through owned tables before enabling publication. Then connect the owned device context and shader/target/parameter/event/queue backing. No root publication, firmware consumption, GPU job, completion or pixels during this offline audit; no reboot required.

Evidence: docs/evidence/2026-10-08-native-notify-root.json; portable audit experiments/t6040-gpu/audit-native-notify-root.py. Binary and both native slice hashes recorded; no Apple instruction bytes embedded in evidence or script.
