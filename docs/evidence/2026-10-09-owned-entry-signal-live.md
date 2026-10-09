# Native fragment entry release and hardware queue state — 2026-10-09

Boot74309e61-bddf-413f-8e73-3f3d7878a07b, kernel7.1.13-m4rch-gpu-contract, module8c8bc6334f4a34bb5abded9c3575d3a4995cb949a1c67c7aa48f87dedf0bc17e. Fresh qualification and combined hold/release trial returned normally. User reports everything normal.

Firmware fragment control cursor/prefetch/producer3; TA2. The intended fragment timestamp1 record changed one byte at page51+347, clearing hold254 (word140 bit62). This verifies native opcode16 handling and target-record release through the installed FW ring. No target/completion bytes changed. Installed queues/context accepted; kicks4; pending flags3/3, pending mask3. No application response or EHLC header.

All six live fault-info/address samples zero. Queue masks0/0 before root/publication ->3/0 by1s through before-stop. Scheduling pause request/ack1/1 ->0/0. No evidence of ongoing scheduling pause; samples cannot exclude transient handled faults between them.

## Additional hardware capture on this boot

While main trial retained GFX power and ASC was stopped, normally unloadable observer selected queues0/1 and restored original selector1, readback verified. Only selector103a8 changed; no kick/reset/resume. It reads the same banked/global registers as matched firmware snapshot16510..16568.

| register | queue0 | queue1 |
| --- | --- | --- |
|21008 ring configuration|12810010000cc001|22810010000d4001|
|21010 raw state|4000000000000|4000000000000|
|21020 raw timeline-like state|ffffffffff|ffffffffff|
|211e0 raw state|3fffffffffffff|3fffffffffffff|

Global210e8/210f0/210f8 are0;21100=4000000000000000. Pause request/ack0/0; fault-info/address0/0. Ring configs match expected addresses/selector/geometry/master. Register21020 is read by matched scheduler code and participates in masked40-bit differences; interpretingffffffffff as the untouched predecessor of timestamp0 is an explicit hypothesis. Raw states do not prove GPU ring fetch, shader launch or completion.

## Next integrated first-NOP diagnostic

Current NOP0 has own dependency bitmap1 at20, previous0 at28. The hardware21020 observation suggests an initial dependency wait. Earlier wrapped-baseline trial also failed, so do not claim this as a proven explanation.

out/owned-first-nop-ready/{prepared,live-candidate} deliberately removes both first NOP dependencies (20 bitmap1->0). Exactly two backing bytes change. Native NOP encoder always inserts an own dependency, so this is a diagnostic departure whose hardware acceptance is unverified. Keep native timestamp1 actual TA/3D work, shared context, selector1, fragment hold254/entry-signal16, shaders/registers/resources/target unchanged. A ready NOP0 could establish timeline0 and unblock real work1; that outcome must be measured.

Matching LLVM/W=1 build clean; Python compile, exact byte diff and compiled-source/module identities checked. Normal Linux reboot required by retained main trial. Fresh qualification then run run-root-envelope.py out/owned-first-nop-ready/live-candidate --graph --run; decode and compare hardware counters/target/completion. No force unload/warm INIT, kernel or default-entry changes. GPU rendering and accelerated desktop remain unverified.

Raw capture out/owned-entry-signal/live-candidate/asc-graph-init/boot-74309e61-bddf-413f-8e73-3f3d7878a07b; decoded out/owned-entry-signal/result-74309e61; observer build/result out/owned-entry-signal/poststop-observer. Private implementation-derived, not clean-room.
