# G16 descriptor render-target and parameter-management inputs

Matched AGX353.14 / Apple25G83. Actual native descriptor loaders, fast-target
geometry and two numeric validators execute in RAM against independent models.
PAC authentication bypassed for unsigned fixture pointers. No hardware touched.

Coverage: 1,024 render-target memory loads; 1,024 fast-target loads; 384 valid
parameter-management loads plus640 intercepted guard failures; 1,024 complete
fast geometry calculations; 1,024 cases for each validator; 512 native
fast-geometry-to-descriptor compositions. Full destination bytes are compared,
including untouched fields; loader source bytes remain unchanged. Binary/code
hashes, trap sites and examples are in the JSON.

This begins tracing where descriptor inputs come from. It does not yet recreate
a valid render target, shader, executable pipeline or job. Apple's render-target
memory object may include tile/parameter-management storage; its name does not
prove any individual field is a pixel attachment or framebuffer address.

## Render-target memory loader

`AGX3DCommandDescriptor::loadRenderTargetMemoryData` 0x895d7b4..0x895d914:
From input target+0x130 load an object; object+0x20 gives a resource; call its
virtual slot0x158 three times. Each result is separately added (u64 wrap) to a
target offset and stored to the descriptor:

| Descriptor destination | Target offset | Width |
| --- | --- | --- |
| 0x8a0 | 0x2a8 + first mapped return | 8 |
| 0x8a8 | 0x2b0 + second mapped return | 8 |
| 0x8b0 | 0x2b8 + third mapped return | 8 |
| 0x8b8 | 0xb0 | 8 |
| 0x8c0 | 0x20 | 8 |
| 0x8c8 | 0xb8 | 4 |
| 0x8d0 | 0xbc | 4 |
| 0x8d4 | 0x114 | 4 |
| 0x8d8..0x8ec, stride4 | 0xc0..0xd4, stride4 | 4 each |
| 0x8f0 | 0x98 | 4 |
| 0x8f4 | 0x18 | 4 |
| 0x8f8 | 0x118 | 4 |

The three map returns are independent synthetic inputs to the audit; it does
not assume the callback is stable or implement its mapping/cache context.
Descriptor+0x8cc is **not** written here. Other field semantics remain numeric.

## Fast-target loader

`loadFastRenderTargetData` 0x895d914..0x895d968 is call-free:

| Descriptor destination | Fast-target source | Width |
| --- | --- | --- |
| 0x8b8 | 0x70 | 8 |
| 0x8c8 | 0x78 | 4 |
| 0x8cc | 0x98 | 4 |
| 0x8d0 | 0x7c | 4 |
| 0x8d8..0x8ec, stride4 | 0x80..0x94, stride4 | 4 each |

This source layout differs from ordinary render-target memory. Fast geometry
below writes only some of those source fields; initialization of+0x80/+0x84/
+0x90/+0x94 is not qualified by the geometry routine alone.

## Fast-target geometry

`AGXFastRenderTargetG16::halComputeGeometry` 0x89e5b2c..0x89e5cf8:
Numeric inputs are target u32+0x10/+0x14 (x/y), +0x18/+0x1c (extents),
+0x20 (sample selector), +0x68/+0x6c (dimension mode), and32-bit sample fields
at+0x24 onwards. Names x/y/extents describe arithmetic, not a complete object ABI.

Compute start tiles x>>5/y>>5, and spans
`(((start + extent + 31) mod2^32)>>5) - start_tile`, subtraction modulo2^32.
If the corresponding dimension mode equals16, shift start and span left1.
Clamp each span to at least1 using unsigned comparison.

Write packed start tiles to+0x98 (x shifted16 OR y, u32 wrap); write the sample
selector to+0x78; pack low10-bit y span and low10-bit x span shifted16 to+0x7c.
For selectors1/2/4/8, OR respectively2/4/8/16 consecutive u32 sample fields into
u64+0x70 at shifts0/4/8/.../60. Values are not nibble-masked before shifting;
fields can overlap. Other selectors leave+0x70 zero. These malformed-input
behaviors do not establish valid sample modes.

For each extent, write a float32 at+0x88/+0x8c. Nonzero extent produces
float32( float32 bits0x3fddb3d9 / float32(extent) ); zero extent uses raw float
bits0x38ddb3d7. The audit exercises integer-to-float rounding, zero extents,
selectors including8, tile boundaries, dimension modes16/32/0 and u32 overflow.
512 compositions execute native geometry then native descriptor copy, matching
both independent models together.

## Numeric validators

Ordinary `halValidateInput` 0x89e63b8..0x89e63f8 accepts input u32+0/+4 <=16384
and u32+8 in1..7. This local check rejects8, although the separate fast geometry
routine has an8-selector packing branch. It is not proof that7 or other
non-power-of-two modes are valid jobs: upstream validation may impose more rules.

Fast `halValidateInput` 0x89e5cf8..0x89e5d30 accepts when
(input0+input8) mod2^32 <=16384 and (input4+inputc) mod2^32 <=16384.
No nonzero minimum or sample test occurs in that method. Overflow is
characterized, not an invitation to use wrapped or zero-sized rendering inputs.

## Parameter-management loader and subtype distinction

`loadParameterManagementData` 0x895d5f0..0x895d7b4:
Input u32+0x2c indexes a u64 vector at pointer+0xa8, with element count u32+0xb0.
The same index accesses another u64 vector at pointer+0x88. Selected values go
to descriptor+0x910/+0x918. The second vector has no independently checked bound
in this method; fixture arrays are large enough for both reads.

Before reads, native guards reject an available span>=2^32, index*8 that is not
representable as signed32, and index*8+8 beyond the available span. A null first
vector means span0. High-pointer overflow/tag paths are excluded; tests use low
unsigned mapped pointers. Guard-failure cases stop before actual panic calls and
leave the descriptor unchanged. The model does not authorize unsafe inputs.

Virtual slots0x158/160/168 return values written at descriptor+0x920/928/930.
Matched AGXParameterManagementVirtual vtable0x7eb3050 binds these to native
getCurrentmTileArrayFWAddress/getCurrentmListArrayFWAddress/
getCurrentvHeapTableFWAddress, respectively. All three native getters return0
and execute as part of the valid-load tests. Input u64+0xb8 copies to+0x938;
u32+0x1d4 copies to+0x948.

The ordinary AGXParameterManagement base vtable0x7eb3610 has external targets
0xc0a8ae0 at those slots, unavailable in this extracted image. Do not substitute
Virtual's zero getters for an actual ordinary subtype or infer that those
firmware address fields can always be zero.

## Toward a drawable job

The checked loaders connect several formerly anonymous descriptor fields to
render-target and parameter-management objects. The common generator consumes
these fields, but this is not full resource preparation. Still needed: actual
render-target allocation/geometry for the selected path, parameter-management
resource construction, shader/state inputs, phase0 model, live mapped contexts,
command sizing, kick-register provenance and firmware completion.

Reproduce:

```sh
python experiments/t6040-gpu/audit-private-render-inputs.py \
  /boot/GPUC003/private-apple/com.apple.AGXG16X /tmp/render-inputs.json
```

## Comparison with the supplied specification

Compared current Downloads/M4-PRO-GPU-HARDWARE-ABI.md, SHA256
`2818ced00eea77f662be9339ee6dae717bd1330e2a46bc927e53190edf6b98db`. The supplied document describes a20-core J616s and the25G83
G16X interface. Our J614s has16 enabled cores; its enabled masks must not be
copied from the20-core example. See gpu-variant-porting-notes.md.

Earlier native audits support its fragment register-list offsets a0/7c0/ee0/1600,
12-byte entries, scheduler record size200, RCE descriptor locations150/158/160/168,
address shift5/count shift43, and channel-reset extentc0. Timestamp40-bit intended
range is consistent with nonoverlapping header fields, although the actual writer
masks47 input bits; out-of-range values may overlap queue identity.

One concrete cursor disagreement: supplied table names queue50 as producer, but
matched native pointer publication loads/advances queue40; reset sets queue50 to
ffffffff. The native submission caller forwards queue40 as the write boundary.
This is checked host publication behavior, not a claim to have resolved every
firmware-owned cursor. See private-queue-pointer and private-channel-reset reports.

The spec does not give the complete register recipe, saved phase0 count boundary,
map50/map58 distinction, input preparation or override behavior now traced. These
are implementation gaps, not automatically document errors. Most command sizes,
completion offsets and dependency record claims are not independently qualified
by the latest audits; matching a few offsets does not validate the entire spec.
