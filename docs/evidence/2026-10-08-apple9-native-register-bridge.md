# Native register bridge for Apple9 shader/state candidates

Offline, private-derived AGX353.14 / Apple25G83. No live job or GPU access.

276 differential trials vary one numeric descriptor dword at a time through
the native 3D generator; 125 words change its observed register lists.
The full observations and baseline backing counts are in the field-registers
JSON. These are numerical dependencies, not standalone semantic definitions.
Conditional insertions, masking and register duplicates are retained.

The candidate bridge executes the complete native common-record copy and then
the native 3D generator with our prepared shader/state fixtures. Fifteen selected
register values match independent expectations. Full phase outputs are recorded
(91/16/23/10 backing entries); phase0's exported prefix count is distinct.

| Candidate input | Common offset | Descriptor offset | Register, flag1 |
| --- | --- | --- | --- |
| background resource word | a0 | 608 | 15368, phase0 |
| background launch byte offset | a8 | 610 | 15370, phase0 |
| EOT resource word | c0 | 760 | 15378, phase0 |
| EOT launch byte offset | c8 | 768 | 15380, phase0 |
| scissor array address | e0 | 4b8 | 15108, phase0, low alignment bits masked |
| depth-bias array address | e8 | 4b0 | 15100, phase0, low alignment bits masked |
| width/height pair | 1c8 | 750 | 15210, phase0 |

Partial-phase background fields638/640 and EOT fields780/788 are supplied
separately; the common copier does not initialize these from the primary pair.
Phases1/2 emit the partial EOT pair; phases2/3 emit partial background.
Register-role labels are corroborated by the pinned Gravity renderer's register
assignments, with address lowbits represented separately as the native flag.
This correspondence is useful evidence, not hardware acceptance.

Gravity's direct VDM/PPP launch fields use 64-byte units. Its submitted
background/EOT launch fields use USC byte offsets; the bridge checks byte
UAPI offsets30c00/30800. The pinned G16 kernel converts these to absolute
USC addresses10000030c00/10000030800 for firmware registers. A present
background also gets bind tagffff800000000000; EOT bind remains0 for this
fixture. The revised native bridge checks these conversions. Earlier bridge
receipts only checked raw offsets and must not be used as firmware-ready state.
All addresses are still offline fixtures.

Correction: the actual pinned G16 donor uses g16_render.rs, which also omits
register10068. The older generic queue/render.rs was the wrong comparison.
G16 kernel queue creation requires a fixed USC aperture at 1 << 40; pinned
Mesa uses that same aperture for gen16/17. The refreshed candidates use it.
This establishes source compatibility, not hardware validation of our mappings.

Still required: actual UAT allocations/cache policy, fixed-aperture mapping,
complete register recipe and parameter/tile storage, matched TA/3D job and
microsequence, completion notification/fence and invalidation/readback.
The retained failed warm INIT remains live on boot
fa78dd48-b214-46fc-8786-cae63897ad78; normal reboot needed before hardware trial.

```sh
python experiments/t6040-gpu/trace-private-3d-field-registers.py \
  /boot/GPUC003/private-apple/com.apple.AGXG16X FIELD_RECEIPT.json
python experiments/t6040-gpu/check-apple9-native-register-bridge.py \
  /boot/GPUC003/private-apple/com.apple.AGXG16X TARGET_DIRECTORY BRIDGE_RECEIPT.json
```
