# SKSM control-slot cleanup and native reuse

Matched AGX353.14 / Apple25G83 private-derived offline evidence.
The native AGX3DCommandDescriptor::complete control-pool cleanup slice runs
from895df04 to895e054 (full addresses in JSON), including optional branches
to callback tails895e360..895e39c. This is not the full complete function.

## Release bookkeeping

| Descriptor CPU field | Firmware pool | Native host stride |
| --- | --- | --- |
| 480 | 1518: final fragment GTPC kick | 40 |
| 450 | 1558: add kicks | 40 |
| 460 | 1598: configuration update | c0 |
| 470 | 15d8: entry signal | 40 |

All numeric offsets/sizes are hexadecimal. A zero descriptor CPU pointer skips
its pool entirely. Otherwise the native slot index is the zero-extended u32
subtraction of pointer low32 minus CPU base low32, divided by the u64 stride.
Our fixtures use aligned in-range slots; high address bits and low32 wrapping
are varied. No native range/alignment check occurs in this reviewed sequence.
Do not treat it as a validation routine for arbitrary pointers.

Under the external pool lock, a nonzero occupancy byte decrements by one; zero
stays zero. If the pool failure flag (+30 relative to pool) is nonzero, native
code loads the pool resource object's +158 pointer and calls external service
0xfffffe000a7e51c8 while still holding the lock. Its actual service semantics
are unavailable in this extraction; this is not proven to be a wakeup or fence.
It then unlocks and clears the descriptor CPU pointer. The separately stored
GPU output pointer is not cleared, the pool search cursor is not reset, and
failure flag is not cleared in this slice. No backing bytes are zeroed here.

## Verification

```
python experiments/t6040-gpu/audit-private-sksm-release.py \
  /boot/GPUC003/private-apple/com.apple.AGXG16X \
  docs/evidence/2026-10-08-private-sksm-release.json
```

1,024 independent fixtures pass:2,048 present and2,048 absent pool pointers,
512 zero-occupancy cases and1,024 failure-flag resource callbacks. Independent
models compare the complete descriptor, firmware object, all occupancy arrays
and exact lock/callback/unlock ordering. Occupancy0/1/2/255 and all optional
pool combinations are covered. Unknown descriptor fields remain intact.

Additionally,64 native allocate/release cycles exercise all four pool request
functions, including configuration-update allocation, and the native cleanup
sequence together. Four-slot pools wrap their cursors sixteen times, generating
256 successful slot releases. Every iteration checks CPU/GPU outputs, cursors,
full object preservation and occupied-to-free transitions. Thus these native
host routines compose for reusable slots, rather than only passing separately.
Locks, resource mapping and optional resource callbacks remain synthetic.
PAC is bypassed for synthetic request pointers; native function and slice hashes
are pinned against the full matched binary.

## Practical boundary

This qualifies host cleanup arithmetic and slot reuse. It does NOT establish
when it is safe to invoke complete. The firmware event/fence path that delivers
completion, real GPU memory ownership, mapping lifetime, ordering/concurrency
and pending scheduler-accounting decrement still require tracing. Do not release
a live command merely because its ring-prefetch cursor advanced. A successful
allocate/release RAM cycle is not a successfully retired GPU job.

Next connect actual completion notification to these cleanup routines and
prepare valid rendering state/shader/target inputs. Retained warm INIT requires
normal reboot before hardware testing. No kernel or hardware changes occurred.
