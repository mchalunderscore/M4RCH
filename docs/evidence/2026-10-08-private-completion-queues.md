# Native G16 KSM completion-queue descriptor geometry

Matched private AGX353.14 / Apple25G83 evidence, offline only.
AGXAcceleratorG16::populateKSMCompletionQueue at89d76c0..89d7948 constructs
four descriptors from accelerator resource pointers1af70/1af78/1af80/1af88.
This is a separate named completion-queue object, not the72-byte general event
ring. Entry payload and consumer/retirement rules are not inferred from its name.

## Descriptor layout

Each descriptor is20 hexadecimal bytes:

| Offset | Width | Source/value |
| --- | --- | --- |
| 0 | u64 | resource+58 object virtual158 return |
| 8 | u64 | resource+50 object virtual158 return |
| 10 | u32 | accelerator+ee58 capacity |
| 14 | u32 | 40 entry stride |
| 18 | u32 | descriptor ordinal0/1/2/3 |
| 1c | u32 | zero |

Offsets/sizes are hexadecimal. Mapping getters are separate and their returns
must not be guessed equal or given CPU/GPU roles solely from this function.
A missing resource clears only descriptor+0, preserving its remaining24 bytes.
This matters if the output was not initially zeroed; do not treat an absent
entry's leftover fields as an initialized queue. The function does not clear
backing, publish cursors, consume completion entries or decrement pending work.

## Allocation-size provenance

The native allocKSMCompletionQueues function reads capacityee58, multiplies
by64 and rounds up to256 bytes for its single-queue allocation argument.
The reviewed instruction slices match independent `(capacity*64+255)&~255`
for256 cases including0,1,3,4,5,255,256 andu32max. This calculation establishes
host allocation geometry only, not valid capacities or entry content.

Static reading of this G16 allocator shows allocation calls for resource slots
1af70 and1af80, returning early if the first fails. The builder supports all
four optional pointers; this audit does not execute the complete allocator or
establish other slots' lifecycle. Avoid assuming four allocated queues simply
because four descriptors can be produced.

## Reproducible verification

```
python experiments/t6040-gpu/audit-private-completion-queues.py \
  /boot/GPUC003/private-apple/com.apple.AGXG16X \
  docs/evidence/2026-10-08-private-completion-queues.json
```

512 complete native builder cases cover all16 optional-resource combinations,
1,024 present and1,024 absent descriptors, distinct random mapping returns and
capacity values. An independent descriptor model compares the entire128-byte
output, unchanged accelerator object, restored stack and exact getter ordering.
Native constant loads execute from the matched binary; constants40/ordinal are
checked against independently specified model values. Function/slice/binary
hashes are pinned. PAC bypassed; resource mapping providers synthetic.

## Next

Trace who receives this descriptor array, completion-buffer initialization,
entry payload and cursor publication, then pending scheduler-accounting release.
The event-machine callback still needs its matched external provider. Valid
shader/render-target inputs and live completion remain necessary for a draw.
No kernel/hardware changes; retained warm INIT requires normal reboot before
hardware testing. No live retirement or rendered pixels established.
