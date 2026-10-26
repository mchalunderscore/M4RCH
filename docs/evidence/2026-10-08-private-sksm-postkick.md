# Native SKSM post-kick record publication

Matched private AGX353.14 / Apple25G83 driver, offline only. The checker executes
AGX3DChannelSKSM::submitBuffer at 0xfffffe000895c1b0..0xfffffe000895c374
continuously, with accelerator +0xee5f bit0 clear. Unlike the earlier NOP
record-patch audit, this covers the 3D caller's ordered optional records,
firmware mapping and channel-pointer publication arguments together.

## Record construction and ordering

All numbers below are hexadecimal offsets except opcode values.

| Order | Opcode | CPU record / GPU address sources | Fields written |
| --- | --- | --- | --- |
| Optional first | 12 | descriptor480 /488 | u32+0=12; u16+4=queue ID; u64+6=prior callback return; u64+e=firmware mapping of descriptor910 |
| Mandatory | 14 | descriptor450 /458 | u32+0=14; u16+4=queue ID; u16+6=descriptor2dc low16; byte+8=scheduler1c low8; u64+9=prior callback return; u32+11=1 |
| Optional last | 16 | descriptor470 /478 | u32+0=16; u16+4=queue ID; u64+6=prior callback return; u32+e=fe |

The first and last record are skipped when their CPU pointers are zero.
Each publication uses channel virtual slot188 with x1=its separately stored
GPU address, x2=its CPU pointer, x3=0. The preceding queue-pointer audit maps
this slot to writeChannelCommandPointer; this checker intercepts that call
and checks its inputs, rather than executing the ring publisher again.
Opcode12 additionally invokes firmware slot2d8 with descriptor910 and x2=0.

The opcode14 patch writes 21 bytes, agreeing with the previous NOP-path prefix
but using the 3D caller's accumulated descriptor2dc count and constant1 at11.
Opcode12 writes22 bytes; opcode16 writes18. A 24-byte fixture checks unknown
tails remain untouched; it does not prove any record's allocation size.

The shared u64 input comes from x22. Earlier native instructions c140/c144
call scheduler slot168 and save its return in x22. The previously audited
G16 scheduler vtable binds that slot to encode3DKickEntry. This checker starts
after that call and supplies the return; it does not prove its semantics or
execute the complete scheduler/firmware handoff. Queue ID is x25 low16.

## Reproducible verification

```
python experiments/t6040-gpu/audit-private-sksm-postkick.py \
  /boot/GPUC003/private-apple/com.apple.AGXG16X \
  docs/evidence/2026-10-08-private-sksm-postkick.json
```

1,024 deterministic randomized cases pass: 1,024 opcode14 records, 512
opcode12 records, 512 opcode16 records, all four optional-record combinations.
Independent struct-based models compare full record backing and exact ordered
mapping/publication calls, including truncated queue IDs/counts/mode fields,
unaligned u64 fields, preserved tails and unchanged descriptor bytes. Binary
and native slice SHA256 are pinned in the checker and JSON.

PAC is bypassed. Firmware mapping and channel publication are synthetic
contracts, and the scheduler input/result is synthetic. The ee5f-set path
tracks descriptor100 through the host ring instead of this opcode14 branch;
it remains outside this audit. These are transport records, not shader jobs
or proof of firmware acceptance, retirement or rendered pixels.

## Next steps

Trace allocation and roles of opcode12/16, and connect real scheduler return
and count bookkeeping to these records. Combine the already checked command,
register generation and scheduler inputs without confusing CPU backing with
GPU addresses. Valid shader/target data, kick MMIO provenance, mapping/cache
policy and firmware completion remain necessary for a first triangle. Current
retained failed warm INIT probe still needs a normal reboot before hardware.
No kernel, boot entry, hardware submission or private binary export changed.
