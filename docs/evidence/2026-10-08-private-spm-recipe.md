# G16 SPM phase register recipe

Matched AGX353.14, binary SHA256 recorded in the JSON. The complete helper
`write3DRCEBufferSPMPhase` at 0xfffffe00089e1df4..0xfffffe00089e2948 and the native
G16 entry encoder executed in emulated RAM for 1,024 fixtures. Independent Python
recipe predicts every (register, flag, value), the complete backing contents and
u16 count/cursor updates. Inputs include all four phase values, both enabled
values, both descriptor+0x897 bit0 values, and randomized zero/nonzero pointer
fields. Inputs, encoder object and unused backing bytes remain unchanged.

This is a register recipe for one helper, not a complete draw recipe. Pointer
authentication is bypassed for unsigned fixture pointers. The sole external
resource map callback receives a synthetic return address. No hardware touched.

## Actual ABI and callers

Helper inputs: x0 accelerator, x1 command CPU backing, x2 descriptor, x3 encoder,
w4 phase, w5 enabled. As with the parent generator, the mangled name contains an
unused channel argument; infer arguments from actual instructions.

The common generator calls this helper for phase1 (0x89df8d0..8e8), phase2
(0x89df8ac..8cc), and phase3 (0x89df7dc..7e0). It constructs phase0 separately.
Phase0 helper cases characterize native arithmetic, not proof the parent uses
that route. All helper outputs still pass through the parent's register override
stage, which this audit does not execute.

## Optional prefix and short path

If enabled is nonzero and phase!=1, prepend:

| Register | Flag | Value source |
| --- | --- | --- |
| 0x14048 | 0 | descriptor u32+0xb60 OR ((accelerator u64+0x6d0 >>31)&0x200) |
| 0x14080 | 0 | ((mapped_address + descriptor u32+0xb98)&0x7ffffffffc0) OR 1 |

Mapped_address comes from descriptor+0xb90 -> object+0x30 -> object+0x58,
virtual slot+0x158. The callback implementation and mapping attributes are not
qualified. Addition is native u64 arithmetic; the mask discards high/low bits.

If descriptor byte+0x897 bit0 is set, append register/value pairs
0x16020/0, 0x160a8/0x20, 0x16068/0x40000 (all flag0), then return.
This path bypasses the remaining recipe; including the optional prefix it has
3 or5 entries. Do not append the ordinary tail on this branch.

## Ordinary sequence

Unless phase3, begin with flag1 writes 0x15378<-descriptor+0x780,
0x15380<-descriptor+0x788. Unless phase<=1, also append
0x15368<-descriptor+0x638 and 0x15370<-descriptor+0x640.

All ordinary paths write flag1 register0x10038 with command u64+0x1f58,
clearing bit16 then replacing it. For phase<=1, replacement is bit16 if either
descriptor u64+0x678 or+0x688 is nonzero, or descriptor byte+0x88e bit0 is set.
For phase3, replacement is descriptor byte+0x88f bit0 shifted16. For phase2,
replacement is zero.

Phase3 optionally writes flag0 register0x16060 with descriptor u64+0x4e0 if
nonzero, then skips the following table. Other phases emit flag1 entries:

| Register | Value source |
| --- | --- |
| 0x15358 | command u64+0x1f60 OR0x20 |
| 0x15330 | descriptor u64+0x678 |
| 0x153c8 | descriptor u64+0x6f8 |
| 0x15340 | descriptor u64+0x690 |
| 0x153d8 | descriptor u64+0x720 |
| 0x15420 | descriptor u64+0x6c8 |
| 0x15430 | descriptor u64+0x700 |
| 0x15428 | descriptor u64+0x6d8 |
| 0x15438 | descriptor u64+0x728 |
| 0x15220 | descriptor u64+0x6a8 |
| 0x15228 | descriptor u64+0x6c0 |

Phase2/3 next write flag1 register0x15308 with descriptor u32+0x7ac OR0x200.

Start final flags from descriptor u64+0x648. Unless phase3, OR0x80000 if
+0x678 is nonzero and OR0x40000 if+0x690 is nonzero; AND0xf0fffffffffffebf;
then OR0x40 if+0x6f8 is nonzero and OR0x100 if+0x720 is nonzero.
These tests are **nonzero**, not absent-pointer flags.

For phase2/3, append flag1 writes 0x15328<-descriptor+0x678,
0x153c0<-descriptor+0x6f8, 0x15338<-descriptor+0x690,
0x153d0<-descriptor+0x720, then OR final flags with0x8000 if+0x668 is nonzero
and0x4000 if+0x680 is nonzero.

Finish with flag1 register0x15318 holding final flags, and flag1 register0x15348
holding descriptor u64+0x650. For phase2/3 clear bits0x4040 in that last value;
phase<=1 preserves them.

Ordinary counts without optional prefix: phase0/1=16, phase2=23,
phase3=10 or11 (depending on+0x4e0). Prefix adds2, except on phase1.
Every append writes the native12-byte entry and advances u16 cursor by12 and
count by1. Random fixture cursors stay within the backing data area; native
out-of-space or metadata-overlap behavior is not qualified.

## What remains

The descriptor fields above are numeric provenance, not verified semantic names
for shader/render target/SPM buffers. Parent phase0 construction, descriptor
preparation, register overrides, command stride, actual mapping contexts,
coherency and live kick offsets remain necessary before submitting a real draw.
Warm INIT failure still needs a normal reboot before further hardware trials.

Reproduce:

```sh
python experiments/t6040-gpu/audit-private-spm-recipe.py \
  /boot/GPUC003/private-apple/com.apple.AGXG16X /tmp/spm-recipe.json
```
