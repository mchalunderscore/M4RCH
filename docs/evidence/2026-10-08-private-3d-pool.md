# Native 3D/FastBlit command backing provenance

Matched private AGX353.14 numeric evidence. 1,024 native pool selections matched:
533 found an available slot and 491 returned full. Those 533 also matched native
mapped-address output and occupancy/cursor bookkeeping slices. Another 512 cases
matched page-rounded allocation-size and capacity arithmetic. External locking,
mapping methods and allocation services were not executed. No hardware accessed.

## Payload address identities

The descriptor initialization paths and matched AGXFirmware/AGXArmFirmwareASC
vtable bindings resolve the previous payload branches:

| Pool | Callback slot | CPU return stored at | First mapped output | Second mapped output/payload |
| --- | --- | --- | --- | --- |
| 3D | 0x2a0 | descriptor+0x438 | descriptor+0x440 | descriptor+0x448 |
| FastBlit | 0x2a8 | descriptor+0x420 | descriptor+0x428 | descriptor+0x430 |

Descriptor byte+0x808 bit0 chooses the FastBlit allocation branch; ordinary 3D
uses the other pool. The second output is derived from resource+0x50 mapping's
slot158 return plus slot displacement. The first uses resource+0x58 mapping's
slot158 return plus the same displacement. CPU return uses the CPU base. Thus
ordinary work payload is a mapped address, whereas the NOP payload's first word
is a command type. Mapping attributes/context semantics remain unqualified.

## 3D pool object

The pool starts at firmware+0x1318. Fields relative to firmware:

| Offset | Role in audited native request |
| --- | --- |
| 0x1320 | backing resource pointer |
| 0x1328 | CPU backing base |
| 0x1330 | one-byte-per-slot occupancy array |
| 0x1338 | stride (low32 used for slot displacement) |
| 0x1340 | capacity |
| 0x1344 | search cursor |
| 0x1350 | external lock pointer |

The native request searches up to capacity slots for occupancy byte0, beginning
at cursor modulo capacity. Search cursor arithmetic is 32-bit. Any nonzero byte
counts as occupied. Full returns zero CPU pointer. Found slot displacement is
slot*stride with 32-bit multiplication; both mapping outputs and CPU return add
that displacement. Cursor becomes (slot+1)%capacity and occupancy byte increments.
Tests preserve the full firmware fixture outside the cursor and slot byte.
The lock and capacity-zero path are outside this tested selection slice.

## Backing geometry

PoolClass<AGFIChannelCommand3D>::createBacking rounds requested-count*stride up
to the supplied page alignment. Capacity is floor(rounded-byte-size/stride), so
it can exceed requested count. Native slices matched 512 supplied-stride cases
with shifts12/14/16. The live stride/page shift and allocation result remain to
capture; no fixed command size is inferred. The resource init uses flags derived
from accelerator+0x18e00 OR0x23; cache-policy semantics are not established.

## Implementation implications

Use a common backing allocation with consistent CPU/mapped-address displacement
and pool accounting; do not substitute a scheduler timestamp for the work address.
The native CPU return and second mapping output point at corresponding slots.
A Linux implementation still needs suitable real mappings and actual 3D contents:
shader, render targets, RCE lists and dependency/event-machine values. These results
do not establish that arbitrary zeroed command backing is accepted by firmware.

Do not mistake a store to some object's +0x220 for this pool's stride source
without tracing its object base. Similar immediate offsets appear in power and
performance structures. Live kick MMIO offsets remain independently unresolved.

Reproduce:

```sh
python experiments/t6040-gpu/audit-private-3d-pool.py \
  /boot/GPUC003/private-apple/com.apple.AGXG16X /tmp/3d-pool.json
```
