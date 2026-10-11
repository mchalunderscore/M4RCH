# Native QoS resource v7

The root-owned `g16_t6040_qos_v7.rs` agrees with the actual matched
`AGXQOSQueue::willSubmit` at8a09134..8a093a4 for the entire0xe40 resource and
64-byte guards on both sides. `qualify_qos_v7.py` executes new sequential native
instructions in RAM with explicit lock, unlock, clock and zero services, then
compares those results with the compiled Rust producer. No corrections to the
Rust producer were needed, and no hardware or frozen sources were touched.

The96 submissions cover six independent queue owners sharing one manager and
one firmware resource. Each owner takes fresh and repeated submissions across
TA/3D/CL, workqueue IDs0/1/2/63/64/65/126/127 and hardware IDs0/1/63/64/126/127.
The manager completion mirrors are supplied independently per submission:
48 cases equal the selected resource DM counter and48 differ. Seeded native
counter values produce14 u32 wrap events and five u64 wrap events. Every step
compares all resource and guard bytes, plus the shared manager submission
counter; successful function return also checks that the native lock and stack
have retired. Native queue initialized/published state stays alive across the
whole sequence, rather than being reconstructed for each call.

For a fresh queue, native publishes the share ratio atresource+c00+4*ID and
scheduler slot at+800+8*ID. Each newly seen workqueue ID publishes the hardware
ID and weight in its8-byte row. Every call increments resource queue count
400+4*workqueue and hardware count600+4*ID. When the selected DM count equals
the native manager c48/c50/c58 mirror, the native clock result is written at
e08+8*DM and aggregate e00 increments. DM count e20+8*DM and manager c60
increment on every submission, with native wrapping arithmetic.

`ManagerState` must be shared by all queue owners using the resource;
`QueueState` belongs to each public queue owner. The production owner supplies
actual hardware ID leases, workqueue IDs, scheduler allocation, time, completion
mirrors, task association, lock/cache/barrier/notification and retirement.
The immutable hardware ID/scheduler slot/weight/ratio binding is an explicit
Linux initial-policy restriction. These bytes are not inferred from firmware
lane numbers, queue UUIDs or freshly invented native registration state.

Nine refusal cases verify no writes: one short initial resource, one short
submission resource, IDs/workqueue IDs outside128, DM outside0..2 and four
changes to an already bound queue's immutable fields. Each binding refusal is
followed by a valid submission compared against an unaffected independent
queue state, exercising preservation of internal continuity as well as bytes.

The qualification also executes the native resource zero request at8a08bc8..d4
(exactly0xe40 bytes with unchanged guards), native ID capacity128 at8a08c04,
and the actual hardware child0+26b8 pointer-binding slice89aa428..434. That
slice reads the manager GPU mapping at manager+28 through accelerator+530.
The manager CPU allocation at+20 used by willSubmit is a distinct address view.
The native registerQueue policy table is pinned as[20,15,4,1,0] at713536b;
weights/ratios in the component remain explicit supplied policy inputs.

The native kernel lock, clock, allocator/mapping and bzero implementations are
service fixtures here; pointer authentication is bypassed. This proves the
resource publication codec and persistent host-state model, not runtime
synchronization, firmware consumption, execution, completion or ID reuse.

New report: `out/gpu-gravity-native-qos-v7-qualification-v1/qualification.json`.
Tracked numeric closure: `docs/evidence/2026-10-11-gravity-native-t6040-qos-v7.json`.
Normal-driver cross compilation and live integration remain parent-owned.
