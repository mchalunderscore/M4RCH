# Native queue component v7

Root prepared `g16_t6040_queue_v7.rs` for the distinct v7 normal-driver batch.
It is not installed or staged. V23 and frozen normal v6 remain unchanged.

`ChannelInputs::write_initial` joins the native c0 channel reset to actual
`AGXArmFirmware::setChannelPriority` policy. The three initial pointers are
explicit native host+88/+90/+98 values, with a separate host+f8 context and
process PID. This API does not infer their allocator mappings or substitute a
queue UUID for PID. `PriorityInputs` receives the native context-priority enum,
requested subpriority and QoS. `firmware_lane()` returns the derived lane. The
caller must choose a Linux policy explicitly; passing lane directly as native
context priority is incorrect. In particular, QoS changes native word40 and
context-priority5 differs from context-priority0 even though both map to lane0.

The separate pointer object needs at least64 hexadecimal bytes, preserves all
untouched bytes, and has capacity at60, producer at40 and sentinelffffffff at50.
`pointer_publication` validates geometry and gives a ring write offset plus next
producer. The caller still owns fresh cursor reads, pointer publication, cache
maintenance, barrier, producer publication and subsequent notification. A full
queue produces no plan. The capacity2..65536 bound is a Linux transport policy
for its 16-bit submitted index; native reset itself copies any32-bit capacity.

`SchedulerInputs` binds an owned firmware slot, allocated QoS hardware-buffer
ID and owning-object byte120. Native initialization clears38 bytes of a40-byte
slot and preserves its tail. `write_config_companions` joins config4a/56 to the
supplied slot/ID and config5a/5e to the same channel's native PID48/subpriority40
getters. The slot is deliberately separate from channel context. Zero QoS ID
can be a valid allocated ID; it does not mean the native constructor sentinel.

New qualification executes actual matched native priority instructions for80
context/QoS combinations, then compares the actual compiled Rust component's
whole channel/pointer/scheduler/config images. It composes frozen reset,
scheduler allocator and pointer proofs without replaying those old audits.
Ten boundary cases cover full/wrapped/corrupt rings, unsupported capacities
and short extents with no output modification. Rust compiles with warnings
denied. Report: `out/gpu-gravity-native-queue-v7-qualification-v1/qualification.json`.
Tracked closure: `docs/evidence/2026-10-11-gravity-native-t6040-queue-v7.json`.

`QUEUE_COMPLETE` remains false. Actual process, QoS and mapping ownership,
complete Work constructors, runtime synchronization and resource retirement
must be supplied by the production integration. Codec agreement is not GPU
execution or permission to release submitted storage.
