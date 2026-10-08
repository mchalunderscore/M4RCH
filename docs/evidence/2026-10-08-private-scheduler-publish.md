# Native scheduler publication and direct kick writes

Matched AGX353.14 private-derived offline evidence. Binary hash and instruction
slice hashes are in the accompanying JSON. No hardware registers were accessed.

## Accounting

1,024 cases execute the actual LDADDAL instruction with Unicorn's MAX ARM64 CPU.
It atomically adds one to queue +0x44, returns the old count and compares that old
count with capacity at +0x10. Equality branches to +0x89dc224 after the increment;
the audit stops before the external diagnostic routine. This is not a blocking
queue-full wait. Greater-than-capacity and wrap inputs do not take that equality
branch; those cases characterize instructions, not valid operating states.

The normal path writes byte1 to +0x98 and caches the original scheduler timestamp
in +0xa0. The previous body audit already established the DMB ISH and timestamp
advancement before this accounting suffix. Full queue-object comparisons preserve
unspecified bytes. Single-thread emulation cannot prove concurrent ordering.

## Direct kick path

1,024 cases compare actual native memory-write traces with an independent model.
With accelerator +0x6d3 bit3 clear, addKicks writes two 64-bit words through the
base held at accelerator +0x358:

- control offset: u32(+0xee28) + 9*u32(+0xee30), with 32-bit wrapping;
- count offset: u32(+0xee2c) + 9*u32(+0xee30), with 32-bit wrapping;
- control value: 0x0020040000021018 OR (queueID <<43), truncated to 64 bits;
- count value: zero-extended 32-bit kick count, written as 64 bits.

This path has no explicit DMB between those two writes. Earlier caller ordering
and the real mapping's memory attributes still matter. The bit3-set path invokes
external service callbacks around equivalent stores and remains unqualified.
The preceding optional trace path also calls external routines and is excluded.
Do not deploy these writes until the MMIO base and dynamic offsets are matched.

## Rejected apparent offset provenance

parsePerfStateMapRegs has stores labeled +0xe28/+0xe2c/+0xe30 in disassembly,
but its destination register is accelerator +0x18000. These therefore write
+0x18e28/+0x18e2c/+0x18e30, not the +0xee28/+0xee2c/+0xee30 fields used by
addKicks. Its source nibbles must NOT be substituted as kick offsets. This
address-base distinction is essential; no dynamic values were inferred from it.

## Next

Trace the actual +0xee28/+0xee2c/+0xee30 initialization and mapping +0x358.
Qualify decrement/retirement and service-assisted paths before building a
reusable scheduler. Live acceptance and rendering-command encoding remain open.
The retained failed warm INIT probe requires reboot before hardware testing.

Reproduce:

```sh
python experiments/t6040-gpu/audit-private-scheduler-publish.py \
  /boot/GPUC003/private-apple/com.apple.AGXG16X /tmp/scheduler-publish.json
```
