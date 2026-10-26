# Native render preparation and donor job comparison

This checkpoint is preparation for a first offscreen triangle, not proof that
only a doorbell remains. No GPU command was submitted and no kernel or boot
entry changed. The failed warm INIT remains retained on boot
fa78dd48-b214-46fc-8786-cae63897ad78. A normal reboot is needed before a live
allocation/transport trial; never force-remove that probe.

Corrected USC placement is1<<40, as required by the actual G16 kernel and Mesa.
Full BG/EOT firmware addresses, UAPI byte offsets and VDM/PPP64-byte units are
now distinguished. See the shader-preparation and native-register-bridge notes.

## Checked native composition

Complete native ordinary geometry -> target loader -> common client record
copy -> full3D register generator now executes as one offline chain. Eleven
expected geometry/storage/shader values match, including macro40004, tile
screen1001, tilemap1001000000, metadata10045d0000, region span50000000,
merge float3cddb3d9 and fixed-aperture BG/EOT addresses. Map providers, topology,
client resources and lifecycle objects are synthetic. This confirms numeric
composition, not a valid live descriptor.

Primary3D exports87 ordered entries; backing has91 because four appended SPM
entries are separate. Other phases have16/23/10. Do not submit all91 as the
primary exported list. Expanded differential tracing covers276 descriptor words;
125 affect observed register lists. Conditional entries, flags and duplicates
are retained. One perturbation per word does not prove all bitfield semantics.

## Actual donor serializers

Pinned kernel3b85d81f656af14d0fc4bea3eef87fe040c424f9 g16_render.rs and
its g16_stamp.rs execute in a standalone Rust CPU adapter. This yields complete
TA/3D work, microsequences and preludes, packed ordered registers, an operand
support record and initialized sparse private/transport storage. No source code
from Apple is copied into the adapter. The input parameter choices are explicit
candidate constants, and donor source/file hashes are recorded.

1080 dimensions/utile/sample/layer combinations match independently calculated
scratch sizes. All158 packed TA/3D register records and four work/microsequence
links are checked. For64x64,1sample,1layer, tilemap and TPC round to16KiB each.
The donor PRIVATE_SIZE is56,442,880 bytes with nine nonzero initialization pages;
operand-pool end is1007ab8000 for candidate start1001000000. Forty alias mappings
and donor transport pages are generated. These sizes/aliases are T8132 donor
assumptions, not confirmed T6040 allocations; never silently publish them.

86 ordered register identities are shared between the native primary87 and
donor87. Their shared order agrees. Native has160b8, donor has a second1731;
those are genuine recipe-identity differences in this source comparison.64 of
86 values agree after native geometry composition. The remaining22 are NOT
all variant differences: many native lifecycle/client fields remain zero and
source inputs differ. The tile-state low default36011 versus donor3717f and gate
prefix60 versus donord5 deserve specific native producer qualification. Preserve
our native recipe rather than replace it with the donor sequence.

See2026-10-08-private-ta-generator.md:128 deterministic native producer cases,
10496 independently checked encoder records and256 metadata links. Fixture
semantics remain incomplete; these are not128 valid rendering workloads.

## Result checking

check-first-render-readback.py rejects an untouched sentinel, wrong byte length,
and mismatched triangle/background samples. Eight tests cover truncated/extra
captures, partial writes, every sampled channel corruption, tolerance and stride.
A positive synthetic test is only a checker test. Actual GPU validation requires
independent queue/event/stamp completion evidence and cache invalidation before
readback; eight sample matches alone cannot prove a completed GPU job. The y-up
linear orientation and quantization remain provisional.

## Remaining integration before actual command submission

- Adapt TA/3D work/microsequence and KSM queue identities to our matched T6040
  graph; donor bootstrap addresses and lifecycle defaults are not relocatable
  facts by themselves. The full native TA producer now executes; qualify complete TA descriptor
  initialization and adapt its exported81/82 versus backing83/84 counts.
  The donor exports65 with71 backing, so its work layout is a comparison only.
- Allocate/map client USC, target, PPP/VDM, parameter/tile and support storage;
  establish address-space/root selection, aliases, permissions and visibility.
- Initialize a real parameter manager and ordinary work queues; match firmware
  return channels and notification handling. Existing32 opcode16 controls prove
  that control processing works, not that render queues are initialized.
- Tie publication to actual event/stamp completion, retain outstanding resources,
  and perform coherent readback. Structural no-job shutdown cannot free render
  resources without a rendering retirement proof.

The donor candidate supplies complete comparison bytes, not a submittable T6040
job. Normal reboot clears the retained failed INIT so live integration can resume.
No macOS handoff is required merely to continue these Linux trials.

```sh
python experiments/t6040-gpu/prepare-gravity-render-job.py LINUX_SOURCE \
 DRAW_DIRECTORY TARGET_DIRECTORY NEW_JOB_DIRECTORY JOB_RECEIPT.json
python experiments/t6040-gpu/check-apple9-geometry-register-bridge.py \
 /boot/GPUC003/private-apple/com.apple.AGXG16X TARGET_DIRECTORY \
 JOB_RECEIPT.json BRIDGE_RECEIPT.json
python experiments/t6040-gpu/check-first-render-readback.py \
 TARGET_RECEIPT.json ACTUAL_CAPTURE.bin RESULT.json
```

Private implementation-derived work; not a clean-room specification. No Apple
binary, firmware TEXT or complete disassembly is exported. Candidate serializers
and manifests are local; no public push was performed.
