# Reproducible Apple9 shader and launch candidates

Prepared in Linux without GPU access. Gravity Mesa source commit
`87ac51d411f0e58a9433567ec2666f457be89e1d`; source/compiler/tool hashes and
results are in the adjacent JSON receipts. These are compiler and serializer
results, not T6040 execution evidence.

Eleven authored program candidates compile identically on three runs each:
three triangle vertex variants, three fragment variants and four simple
compute programs, plus one tile-store helper. The canonical vertex is 282 bytes, 11 GPRs, publication
count 7 and three varying components. The fragment is 154 bytes, 8 GPRs and
three varying components. Both report zero scratch and no preamble.
The constant fragment is 44 bytes with no interpolated inputs. Interior
reference colors and exact small compute outputs are recorded for readback.
Render target orientation, edge rules, tiling and quantization remain unqualified.

The existing tool discarded the compiled metadata. A local reproducible patch
now writes JSON beside each binary: register counts, scratch, preamble bounds,
publication counts, varying layouts, resource bindings/masks and stage flags.
All ten original shader binaries are byte-identical before and after this instrumentation.
Graphics printing `ABI 0` comes from an unused compute profile and is not a
graphics ABI value. Compute bindings are reported through the compute profile
in the original diagnostic; graphics resource fields alone must not be used
to infer compute resource requirements.

Candidate binaries and metadata remain under ignored
`out/gpu-shader-preparation/with-tile-store`. Nothing was installed into
the desktop Mesa or submitted to the GPU.

## Reproduce shader preparation

In the pinned Mesa checkout, apply
`experiments/t6040-gpu/gravity-apple9-tool-metadata.patch`, enable
`-Dtools=drm-shim`, then build target
`src/asahi/compiler/agx_apple9_tiny_tool`. Run:

```sh
python experiments/t6040-gpu/prepare-apple9-shaders.py \
  /absolute/mesa-build/src/asahi/compiler/agx_apple9_tiny_tool \
  /absolute/mesa-source /new/output/directory
```

## Launch serialization

`prepare-apple9-launch.c` links the pinned Gravity parameterized launcher.
It generates vertex/fragment 256-byte records and a compute 1024-byte record
with explicit fixture shader-heap, root-table and launch addresses. Three
candidate records pass entry-target, STOP and zero-padding checks; four invalid
parameter sets fail without writing a destination. The library's diagnostic
call offset points to the entry operand, two bytes after the target header.
No shader body entry, populated roots, VDM/CDM, coefficient/PPP/PBE state or
complete firmware job is implied by these records.

```sh
cc -Wall -Wextra -Werror -Wno-error=sign-compare -O2 \
  -I /absolute/mesa-source/src \
  -I /absolute/mesa-source/src/gallium/drivers/asahi \
  experiments/t6040-gpu/prepare-apple9-launch.c \
  /absolute/mesa-source/src/gallium/drivers/asahi/agx_apple9_launch.c \
  -o /absolute/output/prepare-apple9-launch
python experiments/t6040-gpu/check-apple9-launch-preparation.py \
  /absolute/output/prepare-apple9-launch \
  /absolute/mesa-source/src/gallium/drivers/asahi/agx_apple9_launch.c \
  /absolute/output/launches /absolute/output/launch-receipt.json
```

The warning allowance is for a signed/unsigned comparison in the pinned external
launcher; the local tool builds with other warnings treated as errors.

## Remaining preparation before a draw

Still required: actual GPU allocation/placement and visibility of the prepared
entries/roots/state/target candidates; parameter/tile storage; complete matched
G16S job and microsequence integration; USC-base setup; completion-to-readback.
The tools below prepare several byte-level candidates but do not make a full
render job ready. The retained failed warm INIT needs a normal reboot before a
hardware trial. Offline preparation continues meanwhile.

## Persistent entry image and draw state

`prepare-apple9-stage-image.py` assembles canonical compiled bodies, 0xc0-byte
entry blocks, signed entry branches, roots and launches within a synthetic
4-GiB USC aperture. Entry-to-body displacements and launch operands are decoded
and checked. Matching scalar varying masks/groups are required. No GPU VA is
allocated by this tool.

`prepare-apple9-draw-state.py` extracts the pinned Mesa CF/default-group/direct
VDM serializers and runs them in a CPU adapter. Independent full-byte models
match 256 CF, 256 default-group and 256 direct-VDM fixtures. The canonical full
256-byte PPP record also matches the extracted prepare_draw tail with a
synthetic upload return. Earlier allocations/entry installation are excluded.
Adapter structs deliberately provide only fields needed by these routines;
they are not a native-driver or firmware ABI.

Caller inspection resolves two important pointer conventions: direct VDM's
vertex launch is a USC byte offset divided by 64, while pipeline_word is
0x01000000, **not an entry-header address**. Fragment launch in the PPP group is
also divided by 64. Background/EOT fields in the submit path instead receive
USC byte offsets. Do not mix these units.

## Target and tile-store preparation

The extended tool now compiles eleven candidates, three identical runs each.
The added authored RGBA8 end-of-tile helper follows the pinned Gallium
nir_image_store_block_agx path: 92 bytes, 8 GPRs, publication count4,
image_mask1, no scratch/preamble or ordinary buffer bindings. Image descriptors
therefore remain required despite resource_count0.

`prepare-apple9-target.py` prepares a 64x64 linear RGBA8 target descriptor,
16384-byte sentinel image, scissor/depth-bias records, tile-store image table,
roots/entry/launch and a constant-background candidate. Legacy PBE header
packing matches generated Mesa C in 1024 varied cases; Apple9 address/stride
conversion mirrors the pinned source. Reference interior pixels include offsets
and provisional two-byte-value channel tolerances. Orientation/edge rules and
background dispatch still require hardware qualification.

The background candidate produces (.5625,.625,.125,1), not black. Its dispatch
is proposed, not firmware-verified. Tile-store invocation similarly has not
executed. No actual target or tile/parameter buffers have been allocated.

```sh
python experiments/t6040-gpu/prepare-apple9-stage-image.py SHADERS LAUNCHER \
  NEW_STAGE_DIRECTORY --shader-base 0x800000000
python experiments/t6040-gpu/prepare-apple9-draw-state.py MESA_SOURCE \
  STAGE_DIRECTORY NEW_DRAW_DIRECTORY DRAW_RECEIPT.json
python experiments/t6040-gpu/prepare-apple9-target.py MESA_SOURCE MESA_BUILD \
  SHADERS DRAW_DIRECTORY LAUNCHER NEW_TARGET_DIRECTORY TARGET_RECEIPT.json
```

All arguments above are filesystem paths; each output directory must be new.
Adjacent JSONs record source hashes, output hashes and exact qualifications.
