# Consolidated execution prerequisites, 2026-10-09

The next execution candidate should extend the existing Gravity kernel / Mesa
draw path with the native initialization omissions below, together with the
recovery prerequisite found by the firmware agent. Do not change the owned
draw, ring-header selector, counter baseline, or wake protocol to obtain another
negative trial of those existing hypotheses.

This review is static analysis of the pinned native host and matched firmware,
plus existing captures. It does not establish rendering or repeatable teardown.
No hardware operations or shared implementation edits were performed by this
reviewer.

## Exact recommended initialization batch

All offsets in this table are within the native `hardware` object, reached by
firmware global `0x18e4c0 -> main -> main[0]`.

| Offset | Existing fixture | Native value for this T6040 | Evidence |
| --- | --- | --- | --- |
| `0xf30..0xf3f` | Four zero u32 words | u32 words `(0, 1, 1, 0)` | Host `89cd1b0..89cd1b8`, constant `712dd00` |
| `0x254c` | `0` | `0x3` | Host `89cd604..89cd624`; live ID calculation below |
| `0x2550` | `0` | `0x7` | Same vector producer |
| `0x2554` | `0` | `0x7` | Host `89cd628..89cd640`; live ID calculation below |

The batch also links `power+0x3b50` to an owned, zero-initialized 8-byte
temperature epoch at firmware VA `0xfffffc200014f000`, as detailed below.

The useful hypothesis is that the current fixture omits native event/power
handshakes and an engine configuration value while successfully consuming work
in firmware. Restoring these defaults may allow the already-published owned
work to reach device execution. This is a new integrated hypothesis, not a
claim that the complete native initializer has been reconstructed.

Preserve all preceding owned-hw-completions candidate changes: the actual Mesa
draw bytes, TA/fragment pair, shared context, device mappings, four completion
rings, first-active-state policy, and native timing correction. The bound
recovery pointer prerequisite is part of the same consolidated candidate.

## Recovery prerequisite: retained temperature epoch

The first native recovery86 trial reached shared state1/counter1. After the host
acknowledged state2, firmware faulted at `301a8` on a null 4-byte read. The
firmware agent bound this to an unconditional load through `power+0x3b50`.
It occurs even with the sensor mask/count disabled.

The native allocation descriptor at `89abb94..89abbac` binds host CPU field
`3a0` and mapped field `3a8` to an 8-byte allocation. The shared allocator packs
suballocations to 64-byte alignment (`89a7c8c..89a7ca4`) and clears its allocated
block before binding the fields (`89a7e20`, `89a7e7c..89a7ea4`). Native publication
at `89cc55c` and `89d0fa0` stores the converted mapped VA at `power+3b50`.
The epoch changes when the native host reads and resets temperature statistics;
the firmware consumer reads its first u32 and resets recorded extrema when it
changes. It is not a completion counter.

The integrated preparation reserves an aligned 8-byte `temperature_epoch`
suballocation at `status_b` allocation offset `0xf000`, beyond the native
`status_b` object extent `0xe440` but inside its existing 64KiB owned backing.
This is a separate semantic allocation in page-rounded padding, not a native
status field. It introduces no extra owned pages or changes to pool/render
indices. Its full 8 bytes remain zero, and the pointer remains valid for the
whole retained graph lifetime. Preparation rejects a nonzero sensor mask at
`power+3b58`, a nonzero count at `power+3b60`, or a prepopulated sensor region;
sensor calibration and a nonzero sensor table have not been qualified.

The firmware agent's embedded audit executed 128 native pointer-publication
and matched zero-sensor consumer cases, compared full power images, and
reproduced the exact null read at `301a8`. Allocation/cache services were not
executed. The complete audit is embedded in the integrated preparation receipt.

## Native `f38` default has direct consumers

The native vector's bytes are
`00000000 01000000 01000000 00000000`. Unlike merely finding a nonzero constant,
the word at `hardware+0xf38` has direct consumers in the matched firmware:

* `33318..333f4` loads it through `global18e4c0 -> main -> hardware` and, when
  nonzero, registers/enables handlers `29f2c` and `29efc` through the firmware
  event services. The zero branch skips these registrations and disables the
  later three event sources. The complete peripheral meaning of these event
  sources is not asserted here.
* `2beac..2bed4` gates the write `primary+0x5958 = 7` and the poll of
  `primary+0x5960 & 7`.
* `322c8..322f4` gates the write `primary+0x5968 = 7` and the poll of
  `primary+0x5970 & 7`.
* `347ac..347d4` and `39598..395bc` gate u32 writes of `7` to `+0x1010` in
  the two register blocks reached through globals `18f9a0` and `18f9f0`.

Captured DATA from `owned-hw-completions`, boot
`520da35a-487e-4575-97b3-af12afa2936c`, binds `18f9a0` to descriptor slot35,
physical `0x288e00000`, and `18f9f0` to slot37, physical `0x288e40000`.
These are **not** slots22/32. Both base pages are already writable in the graph.
The primary handshake addresses are within the already-writable
`0x288004000` page. The branches identified here do not require expanding the
existing MMIO mapping set. Actual handshake completion still needs observation.

The same-vector `f34=1` is retained as the native initializer's value; no direct
consumer of that specific word has been bound in this review. Do not describe
it as an independently established execution gate.

## T6040 masks are derived from its captured ID

The idle recovery trial captured `raw_d04018=0x01320311` at all four existing
sampling points, in:

`out/recovery-idle/live-candidate/asc-graph-init/boot-e3501874-8c10-47f2-92e1-a8de666e7caf/dmesg-after.log`

The native `AGXAcceleratorG16::readChipInfo` reads this value from SGX offset
`0xd04018`, physical `0x288d04018`. Instructions `89d6818..89d686c` derive the
three counts below. Same-image vector constants at `712d8d0/712d8d8` contain
signed shifts `(-20,-24)` and `(-4,-8)`; these resolve the SIMD nibble extraction.
The resulting `AGXGPUCoreConfig+48/+4c/+50` fields are copied into accelerator
`+4c8/+4cc/+4d0` by `89a0ce4..89a0cf8`.

```text
R = 0x01320311
A = ((R >> 16) & 15) * ( R        & 15) = 2 * 1 = 2
B = ((R >> 20) & 15) * ((R >>  4) & 15) = 3 * 1 = 3
C = ((R >> 24) & 15) * ((R >>  8) & 15) = 1 * 3 = 3
mask(n) = low32((1 << n) - 1), saturated to 0xffffffff for n >= 32
hardware[254c,2550,2554] = [3,7,7]
```

These values are not inferred from the 16 enabled USC cores, two clusters,
donor M4 defaults, or ADT voltage-table counts. The native ID register gives
their exact producer inputs.

Firmware `2f864..2f880` copies the three words to runtime configuration
`18f6d0+141c/+1420/+1424`, respectively. `aa58..aac8` consumes the third mask:

```text
primary[0x1710] = ((maskC << 3) & 0x10) | ((maskC & 1) << 12)
               = 0x1010
```

The current zero fixture programs zero there. The earlier `aac8` permission
fault and its later mapping fix already establish this write path; the new
finding is the omitted native value. Consumers of the first two masks beyond
their runtime copy are not independently bound here.

## Exclusions and corrected interpretation

* `hardware+2578=1`, `25a0=1`, `25ac=1`, and `25b0=1` are additional native
  initializer constants absent from the fixture. `2578` has no bound matched
  consumer in this review. `25a0/25ac/25b0` are copied to runtime configuration
  but have no bound execution consumer. Exclude them from this batch rather
  than treat every native constant as a demonstrated prerequisite.
* `setupMMUConfig` is not a reset recipe. The G16 implementation at
  `89e67f8..89e6d28` returns when `d08000` is nonzero. The previously audited
  disabled case programs the table and enables it; it does not validate or
  replace an already-enabled table. `configureMMUForBoot` at `89d9b6c` is a
  no-op in this image. Preserve the owned context mapping and retirement rules.
* The existing analyzer's `firmware_pending` flags are better understood as
  register-shadow dirty/save-restore bookkeeping. The config handler writes
  selected-queue `21008` at `198c0`, then sets flag bit0 and the queue mask.
  The kick handler writes `21018` at `19484`, then sets bit1 and the mask.
  Therefore flags `3` and mask `3` do **not** prove hardware writes are still
  deferred. Helper `15e60` saves selected-register images at `16474..16604`
  and restores/clears the shadow state at `160d0..1610c`.
* Header selector1, zero-baseline/dependency changes, first-NOP ordering, and
  the recorded warm START / START+INIT220 / held-START trials remain known
  negatives. Their receipt alone should not justify another live trial.

## Required observations for this batch

Before publication, verify the five changed u32 values and existing mappings
against the receipt and bind any recovery object through its native producer
and owned lifetime. The recorded native vector changes only `f34/f38`; its
other two words remain zero.

After the serialized trial, check runtime masks `3/7/7`, SGX `1710=1010`,
firmware progress/fault data, native recovery state transitions, and actual
device completion/target bytes. Channel consumption, natural kick counts,
shadow flags, and successful native recovery alone are not rendering evidence.
Once recovery itself repeats on the same owned allocation, execution can be
tested without repeating the failed wake/rebuild mechanism.

## Prepared artifact

`experiments/t6040-gpu/prepare-native-init-recovery.py` generated
`out/native-init-recovery/prepared/graph`. It checks the pinned host, normalized
firmware TEXT, four serialized ID samples, native instruction/constant sites,
the firmware agent's successful static epoch audit, source input hashes, and
the explicit owned pointer graph. There are 11 changed graph bytes across the
two initialization ranges and epoch pointer. All 13 root-channel cursor/ring
regions and `backing.bin`, `job-data.h`, and `render-data.h` are unchanged.
The generated C header was reconstructed and compared with the full
1,130,496-byte graph; all 69 arena pages are retained.

This output intentionally retains the original work producers and
`work_publication` metadata. The separate recovery preparer owns idle producer
suppression and deferred publication. The native initializer script does not
publish work, interact with hardware, or alter the shared driver implementation.

## Identities and baseline

* Native host SHA256:
  `3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e`.
* Normalized firmware TEXT SHA256:
  `190cef1946a23dfbde180592629631c3b28d0509a17eb76108b7c9a52accd9ac`.
* Baseline graph:
  `out/owned-hw-completions/prepared/graph/{graph-before.bin,graph-receipt.json,preparation.json}`.
* Baseline execution analysis:
  `out/owned-hw-completions/result-520da35a/result.json`.
* Disassemblies:
  `out/private-apple/agx-disassembly.txt` and
  `out/private-apple/live-text.dis`.

Native host addresses above omit the common `fffffe0000000000` base;
firmware addresses are normalized offsets. Numeric offsets from other firmware
builds must not be substituted.
