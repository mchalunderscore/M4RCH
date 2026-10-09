# Native scheduler-state allocation and configuration

Offline review of matched Apple25G83 / AGX353.14 driver, SHA256
`3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e`.
Source baseline `d98fee4`; comparison is against the existing
`out/recovery-dispatch/candidate/asc-graph-init` bytes. No candidate edit,
hardware operation, wake trial, recovery or submission was performed.

## Result

The provisional seed's first `0x38` bytes match the native scheduler-state
initializer when the supplied owning-object byte `+0x120` is `2`. That value
is an input to the constructor, not a native constant. The constructor clears
exactly `0x38` bytes in a `0x40`-byte allocated slot; it preserves the final
eight bytes. The existing zero tail is an allocation policy, not a detected
encoding error.

The native config companions are now identified. They are not UAT ASID fields.
There is a concrete discrepancy between the staged state and the staged config:
native getters applied to these state bytes would produce different PID and
subpriority values. Their actual process/policy values remain unresolved.

| Native field | Proven producer | Current staged values |
| --- | --- | --- |
| Scheduler byte `+0x26` | Queue `+0x490` object, byte `+0x120`, at `0x8989bbc..0x8989bc8` | `2`; actual owning-object association and producer unqualified |
| Config `+0x4a` | Queue `+0x8b8`, firmware resource mapping plus allocated slot offset | Shared `0xfffffc2000b18200`; mapping and actual VM association remain supplied |
| Config `+0x56` | Queue `+0x898` `AGXQOSQueue`, hardware-buffer ID at `+0x10` | `0`; native init uses `0xffffffff`, and later ID allocation can assign zero |
| Config `+0x5a` | `AGXChannel::getPid`, mapped channel state `+0x48` | Config `0`, state `1/2` |
| Config `+0x5e` | `AGXChannel::getSubPriority`, mapped channel state `+0x40` | Config `0`, state `1` |

The uploaded ABI's “Channel UUID” label at channel state `+0x48` conflicts
with the matched native PID chain. This is the same mapped channel-state class:
queue `+0x498` is copied to host channel `+0x4c` at
`0x897fab8/0x897fae8`; `resetChannelState` copies host `+0x4c` to mapped
state `+0x48` at `0x897deec..0x897def8`; `getPid` reads that exact word at
`0x897de60..0x897de70`. Native `0x89802f4` publishes the mapped CPU pointer
to channel `+0x58`. The current builder writes `qid+1` at state `+0x48`
(`prepare-owned-scheduler-pair.py:43`), which is an experimental supplied PID.
The producer of queue `+0x498` and its process association remain outside
this qualification. No replacement PID is established.

## Native allocation and service boundaries

`AGXCommandQueue::allocateSchedulerState`, `0x89897cc..0x8989bf8`, operates
on the embedded firmware pool at firmware object `+0x1158`. Native firmware
construction at `0x89d2d50..0x89d2dc4` installs the pool vtable and empty
allocation structures. The actual init caller `0x89cf024..0x89cf06c` passes
stride `0x40`, flags `9`, caching `1`, null task and shrink mode `0` to the
actual pool initializer `0x89afa80..0x89afb44`. Kernel-global page geometry,
task lookup and registration remain explicitly supplied services.

Pool init stores accelerator `+0x140` to pool `+0x10`, firmware `+0x1168`.
The allocator's initial nonzero gate checks this event-machine association;
it is not a free-slot count. The free-block bitmap is firmware `+0x11e0`;
each selected block contains 256 subslot bits at `+0x11e8`, represented by
four 64-bit words. The allocator chooses the lowest available block/bit,
derives an allocation index and remainder using slots-per-allocation
`+0x11b8`, checks the storage-array extent/bias, and retains its resource.

It publishes resource/CPU/global-index/firmware pointers to queue
`+0x8a8/+0x8a0/+0x8b0/+0x8b8`, consuming the free bit before preparing
mappings. The firmware pointer comes from resource `+0x50`, virtual method
`+0x158`; the CPU pointer comes from resource `+0x60`, method `+0x138`.
Actual allocation, address-space construction, page-table installation,
permissions, aliasing and reference-count behavior are service boundaries.
They are not proved by supplied RAM pointer returns.

The actual `AGXInternalResource::prepareMappings` body at
`0x89ed740..0x89ed7c0` executes in the audit. It prepares external mapping
objects `+0x50` and `+0x58`; second preparation failure completes the first
mapping. Successful preparation increments resource `+0x38` under its lock.
Lock and mapping operations remain checked services. Failure returns false
**after pool-slot consumption and queue-pointer publication**; this function
does not roll them back. Initialization of the subslot occurs only on success.
The actual `ensureReclaimableResources` caller sets queue accepted byte
`+0x5f0` only after allocation success.

The actual config slice `0x895be40..0x895bf04` copies the owner pointer and
QoS ID, and invokes the real, pinned channel getters. Owner lookup is an
explicit metacast service. G16 ordinary and SKSM TA/3D vtables all resolve
slot `+0x1f0` to `getSubPriority` and slot `+0x1f8` to `getPid`.

Queue init's metaclass global `0xc6e8048` is `AGXQOSQueue`. The native caller
`0x898e8bc..0x898e920` calls its actual initializer
`0x8a096a0..0x8a09718` and publishes it at queue `+0x898` only on success.
Metaclass allocation, inherited hardware-buffer init and lock allocation
remain supplied services. Native QoS `prepare` later calls
`AGXHardwareBufferIDManager::alloc`; that manager writes the allocated
hardware-buffer ID to object `+0x10` at `0x89ec4c0`. This later ownership and
registration policy is static evidence only and was not emulated here.

## Replay and checks

Run from the repository with the already installed Unicorn Python dependency:

```sh
python3 experiments/t6040-gpu/audit-native-scheduler-state.py
```

It reads the pinned private driver, writes only numeric
`out/native-scheduler-state/report.json`, and compares the current candidate
without changing it. Candidate byte extent, alias extent and backing SHA256
must match `preparation.json` before the comparison is accepted.
Optional `--macho`, `--candidate` and `--output-dir`
select equivalent offline inputs/outputs. It exports no private instruction
bytes or disassembly. The checked-in JSON records script/binary/range hashes,
decoded vtable slots, candidate hashes, service boundaries and counts.

Passing checks: 265 successful allocator runs; 34 failure runs; three actual
bound-check trap paths; 256 joined allocated-state/channel PID/config chains;
all 256 possible owner-byte values; eight queue-reset and eight pool-constructor
cases; three native pool-init geometry cases; three QoS init/association cases.
Complete fixture objects and their surrounding untouched bytes are compared
against an independent numeric model. PAC is bypassed, locks are sequential
RAM services, and no GPU, DMA, cache behavior or concurrency is simulated.

## Actionable remaining work

1. Correct semantic PID/subpriority naming and join config construction to
   its channel getters in the offline builder/model. Qualify intended
   process/PID and subpriority inputs before changing an execution candidate.
2. Join the scheduler state's actual owning task and resource mappings to the
   installed UAT context. Neither a shared firmware pointer nor header selector
   `1` proves that association. Byte `+0x26=2` remains a supplied owner input.
3. Qualify ownership of the QoS hardware-buffer ID published at config `+0x56`.
   Zero is not the native constructor sentinel, but it can be a legitimate
   allocated ID; do not replace it with `0xffffffff` by inference alone.
4. Preserve allocation/mapping failure accounting and resource retirement
   when implementing reuse after submitted work. Serializer/replay agreement
   does not establish firmware acceptance, completion or safe teardown.

None of these findings demonstrates the cause of the current idle phase2
recovery failure. Healthy recovery remains the prerequisite for another
execution trial.
