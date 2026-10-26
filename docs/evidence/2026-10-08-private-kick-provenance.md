# Kick-register provenance: distinguish the two accelerator field banks

Private-derived matched AGX353.14 / Apple25G83; offline only.

The similarly spelled offsets in `parsePerfStateMapRegs` are **not** the kick
register configuration consumed by `AGXKSMKickQueueG16::addKicks`:

| Native path | Base instruction | Effective fields |
|---|---|---|
| Performance-state parser | `89d6380`: accelerator + `0x18000` | `0x18e28`, `0x18e2c`, `0x18e30` |
| Direct kick | `89dc2b8`: accelerator + `0xe000` | `0xee28`, `0xee2c`, `0xee30` |

The parser extracts low and bits16–19 nibbles from successive 32-bit MMIO
values into paired 32-bit fields, starting at accelerator `0x18e08`. Native
slice `89d646c..89d64ec` executes six such pairs in 1024 randomized cases.
Whole accelerator fixture comparisons verify those exact stores and preservation
of every other byte, including all three actual kick configuration fields.
Pointer registers are supplied at the slice entry; the two base-forming
instructions are separately inspected, not executed in that slice.

The complete call-free leaf `halSKSMGetKickIDQueueIDConfig` at
`89e7fc0..89e7fd4` writes 64-bit values `0x28` and `0x7f` to its two output
references in 1024 cases. Its name and downstream geometry suggest a 40-bit
shift and seven-bit queue-ID mask; this does not establish MMIO register offsets.

## Additional rejected candidates

The apparent store to `+0x358` at `89cc98c` targets a firmware output object:
`89cc7c8` loads firmware object `+0x380`, then `89cc7cc` sets the destination
base to that output +`0x12c`. It is not a store to accelerator MMIO base358.
The apparent vector stores at `896e994`/`896e9ac` need their own base provenance;
they must not be assumed to initialize actual kick offsets either.

## Run and next work

```
python experiments/t6040-gpu/audit-private-kick-provenance.py \
  /boot/GPUC003/private-apple/com.apple.AGXG16X \
  docs/evidence/2026-10-08-private-kick-provenance.json
```

All 2048 slice/leaf cases pass. The parser produces performance-map nibbles,
not usable kick addresses. Continue resolving actual `ee28/ee2c/ee30`
initialization and the accelerator358 mapping provider before implementing a
hardware doorbell. No hardware writes, firmware acceptance, render execution or
kernel change is proved. Retained warm INIT still requires a normal reboot
before new hardware experiments. No private binary/disassembly exported.
