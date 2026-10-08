# Native 3D configuration record construction and pointer publication

Private-derived matched AGX353.14 / Apple25G83, offline only. This extends the
scratch/config-prefix audit through the remaining record fields and the real
channel-pointer publisher. The checker executes895bd00..895bf44 continuously,
calling native writeChannelCommandPointer at8981048..8981128 through the actual
G16_SKSM channel vtable slot188. No hardware submission occurs.

## Remaining record fields

All offsets/values below are hexadecimal. Earlier prefix fields, including
opcode15, queue mappings/ID, scratch enable26 and scratch value2a, retain the
previous independent model.

| Record offset / width | Value |
| --- | --- |
| 36 / Q | conditional supplied x26 pointer, otherwise0 |
| 3e / Q | descriptorb58 object'sb0, otherwiseffffffffffffffff |
| 46 / I | descriptorb60, otherwiseffffffff |
| 4a / Q | descriptor60 lookup object's8b8 |
| 52 / I | descriptor2f6 bit0 |
| 56 / I | lookup object's898 object's10 |
| 5a / I | descriptor170 object's virtual1f8 return |
| 5e / I | descriptor170 object's virtual1f0 return |

The conditional branch tests w27 bit0. The preceding native slice bcbc..bccc
sets w27=1 when descriptor2e1 bit0 is set, otherwise loads descriptor180 byte.
This audit supplies w27 at the reviewed entry and exercises both branches; it
does not execute that earlier derivation or x26's command-payload lookup.
No semantic name is assigned to these conditional/provider values yet.

Two actual direct calls to beaf410 look up descriptor60 with c6e6298 metadata;
the checker validates the arguments and supplies a synthetic owner. Callback
and provider returns do not prove mapping, event/stamp identity or validity of
a real render configuration. Both channel170 callback returns are synthetic.
Actual descriptor getDataMasterff and payload getter remain native.

## Publication is executed, not intercepted

After building the record, the native caller supplies:

```
x0 = channel
x1 = descriptor468 (GPU address)
x2 = descriptor460 record backing (fixture record pointer)
x3 = 0
```

The checker enters after descriptor460 was loaded into x24; it supplies that
record pointer. It verifies the publication arguments and executes the actual
native publisher. Queue-state60 capacity, producer40 and read cursor0 establish
space. The publisher appends the GPU pointer to channel68's array, executes
DMB ISH and advances producer40 modulo capacity. CPU x2 is not substituted for
the GPU address. No optional tracking object is requested because x3=0.

4096 ring fixtures at capacities2/3/16/256 cover all positions including
wraparound. Read cursor initially equals producer, so these are non-full
publications; earlier queue-pointer audit separately covers full-ring behavior.
Full ring/state bytes match the independent append/cursor model, and no other
channel/descriptor/scheduler/shared-counter bytes change except the already
modeled caller store to descriptor2e8.

## Scope and verification

```
python experiments/t6040-gpu/audit-private-3d-config-publish.py \
  /boot/GPUC003/private-apple/com.apple.AGXG16X \
  docs/evidence/2026-10-08-private-3d-config-publish.json
```

4096 combined cases pass: native scratch method/getter, descriptor store,
complete common config helper for comparison, complete inline3D config record
construction and native pointer publication. 2048 conditional-present and2048
conditional-absent cases pass. The common and inline3D constructors execute
separately against original backing, not as a claimed real call sequence.
Fullc0 record backing compares against an independent struct-based model;
bytes86..bf remain unchanged. This still does not establish the wire payload
extent; native allocation stridec0 differs from the supplied88-byte wire extent.

Matched binary, native function ranges and actual vtable bindings are pinned
or recorded. PAC is bypassed; owner lookups and selected callback values are
synthetic. DMB/LDAR execute in emulator RAM, not a GPU/DMA concurrency test.
No complete3D submit, hardware doorbell, firmware consumption, notification
routing, fence or draw is proved.

## Next gap

Configuration publication ends at895bf44 before optional ee5f/descriptor181
host-gate work and scheduler submission. Continue the enclosing submit path to
connect this configuration to actual scheduler entry creation and the already
audited opcode12/14/16 post-kick ordering. Cache/mapping policy and valid shader/
target inputs remain needed, as does actual completion readback. Retained failed
warm INIT still requires normal reboot before new hardware trials.
