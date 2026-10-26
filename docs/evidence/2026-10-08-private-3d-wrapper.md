# 3D scheduler wrapper input provenance

Matched private AGX353.14 driver. 1,536 native getter cases, 512 native 3D
argument-assembly cases and 512 caller payload-assembly cases match. Hashes and
vtable bindings are in the JSON. This is offline RAM emulation and static call
provenance, not live 3D execution.

## Descriptor callbacks

The matched 3D descriptor vtable binds slot1e0 to getEventCommandStruct, returning
descriptor+0x210, and slot1e8 to getEventBarrierStruct, returning descriptor+0x218.
TA has the same offsets through distinct getter addresses. CL uses slots1b8/1c0
and offsets1c4/1cc. These objects are inline descriptor data, not callback-returned
GPU mappings. Native hint/add instructions are executed; emulation stops before RET.

The scheduler G16 vtable binds slots160/168/170 to TA/3D/CL encoders. The native
SKSM 3D submit caller dispatches scheduler slot168. This must not be confused with
a descriptor's slot168 or the earlier getDataMaster slot188.

## 3D common-encoder inputs

After the event/barrier callbacks and QOS lookups, the native call-free tail
passes:

| Argument | Source |
| --- | --- |
| x0 | scheduler object |
| x1 | descriptor+0x210 event command |
| x2 | descriptor+0x218 barrier record |
| x3 | descriptor+0x820 RCE input |
| x4 | descriptor+0xa98 aperture input |
| x5 | descriptor u64+0x168, or fallback below |
| x6 | original caller payload wrapper |
| x7 | stack+0x14, QOS assembled earlier |
| stack0 | original caller notification-mask reference |
| stack8 | 1 if descriptor byte+c44 equals3, otherwise byte+4c lowbit |
| stack9 | descriptor byte+b48 lowbit |

A zero descriptor+0x168 value triggers the fallback load:
`*( *(descriptor+0x10) + 0xfd48 + ((u32(descriptor+0x964)&127)*8) )`.
The audit checks both branches and all argument registers and stack writes. The
auxiliary value's semantic role remains unproven. It is not guessed as a fence.

## Native caller payload

The SKSM caller stores two words: its current x25 value and channel+0x80. It
builds a pointer/count2 wrapper and clears four notification words. A later caller
path can set notification bits; the local payload audit stops before that path.
This is a pointer pair for ordinary work, unlike the NOP caller's command-type
and channel-state pair. The first word comes from descriptor+0x430 on one native
branch or descriptor+0x448 on the other branch joining at +0x895bc30. The field
construction/mapping provenance and what firmware expects at that address still
need tracing. Channel+0x80 was separately qualified as the channel-state GPUVA.

## What this enables and what remains

These results connect the checked common encoder to actual 3D wrapper locations.
The earlier QOS assembly still depends on external resource lookup and internal
state; it was not executed here. Constructing the descriptor is a separate task:
RCE buffers, aperture allocation, work-command backing, shader and render target
must be populated with valid GPU-visible inputs. None is established merely by
knowing descriptor offsets. Exact kick MMIO mapping/offsets and firmware completion
remain unresolved. The retained failed warm INIT probe requires reboot before a
hardware trial.

Reproduce:

```sh
python experiments/t6040-gpu/audit-private-3d-wrapper.py \
  /boot/GPUC003/private-apple/com.apple.AGXG16X /tmp/3d-wrapper.json
```
