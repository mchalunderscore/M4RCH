# Native SKSM transport pools and allocation provenance

Private-derived matched AGX353.14 / Apple25G83. No hardware execution.

## Three record identities and descriptor storage

Static native call/argument/store checks connect the preceding post-kick audit
to named firmware request functions:

| Opcode | Request method | Descriptor CPU/GPU outputs | Firmware pool base | Stride field/source |
| --- | --- | --- | --- | --- |
| 12 | requestChannelCommandAddFinalFrgGTPCKick | 480/488 | 1518 | 1538 <-270 |
| 14 | requestChannelCommandKSMKickQueueAddKicks | 450/458 | 1558 | 1578 <-278 |
| 16 | requestChannelCommandKSMKickQueueEntrySignal | 470/478 | 15d8 | 15f8 <-288 |

Offsets are hexadecimal, relative to the descriptor or firmware object named.
The caller passes the address of the GPU output field in x1, receives CPU backing
in x0 and stores that separately. The pool initializers copy a u64 runtime stride
from the listed firmware source fields. Request functions use its low32 bits.
No constant allocation size is established by these copies; defaults270/278/288
still need provenance. The opcode14 24-byte spec extent is not proved solely by
its 21-byte native patch. Opcode12/16 names do not prove detailed GPU semantics.

## Complete request functions

The checker executes all three native functions, including their prologue,
branches, selection/address/accounting and epilogue. External lock/unlock and
resource mapping getter are synthetic contracts. Relative to each pool base:

- +8: resource object; its +50 object supplies virtual slot158 GPU mapping.
- +10: CPU backing base.
- +18: per-slot occupancy bytes. A null pointer returns zero without locking,
  without changing the output GPU-address field or failure flag.
- +20: stride; selection multiplies low32 stride by slot with u32 wrapping.
- +28: u32 capacity; +2c: u32 search cursor; +30: u32 failure flag.
- +38: lock object passed to external lock/unlock.

Under the lock, scan up to capacity slots, wrapping the u32 scan cursor before
modulo capacity. Only an occupancy byte equal to zero is free. On success:
write resource mapping +offset to the GPU-output pointer, advance cursor to
(slot+1)%capacity, increment selected occupancy from0 to1, return CPU base+offset.
Failure flag reflects whether the resulting CPU address is zero. On full or
zero-capacity pools, return zero, set failure flag1, leave output GPU address
unchanged and unlock. The request does not clear or construct record backing.
No retirement/release behavior or lock implementation is inferred here.

## Verification and limits

```
python experiments/t6040-gpu/audit-private-sksm-pools.py \
  /boot/GPUC003/private-apple/com.apple.AGXG16X \
  docs/evidence/2026-10-08-private-sksm-pools.json
```

3,072 cases pass, 1,024 per complete function. Independent models compare full
firmware fixture bytes, occupancy, output pointer, return value, restored stack
and exact lock/map/unlock ordering. Capacities0/1/2/3/16/256, u32 search wrapping,
free/full/absent backing and u32 offset wrapping are covered. Synthetic strides
include24/32/64/88 and0xfffffffc; the last characterizes arithmetic rather than
valid native allocation geometry. No mapped backing is dereferenced by these
request functions. Static checks additionally validate native caller BL targets,
GPU-output argument, CPU-output store, stride source/store instructions and hashes.

PAC is bypassed. Single-thread RAM cannot establish concurrency, DMA mapping
attributes, lifetime, cache coherency or live firmware acceptance. Opcode12 is
requested when descriptorc44 equals2 and its CPU pointer is absent in the inspected
prepare path; other branch conditions and full preparation are outside this audit.

## Next

Resolve default stride initialization, release/retirement, and real shader/state
inputs. Combine the qualified pool outputs with the checked 3D construction,
register generator and scheduler/publication path. Still no complete valid draw
or accelerated desktop. The retained warm INIT probe needs normal reboot before
hardware experiments. No kernel, package or boot-entry changes in this pass.
