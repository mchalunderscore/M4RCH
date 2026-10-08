## Descriptor-derived3D scheduler integration — 2026-10-08

All16 paired candidates now derive dependencies,flags,RCE kind,auxiliary fallback and payload from constructed descriptor plus explicit provider bindings.19 invalid inputs rejected. Separate full native wrapper audit covers1,024 cases. Queue timestamp and descriptor timestamp kept distinct; payload448 kept distinct from register mapping440. See native-3d-scheduler-bindings.md. No live job.

## Ordinary3D event/control and aperture integration — 2026-10-08

16 paired candidates retain80 list/scheduler links and64 independently expected TA FW values. All16 now check3D event/control with event boundary cases, native aperture records counts0..15, descriptor timestamp and aperture outputs, and scheduler aperture derived from updated descriptor.18 malformed inputs rejected. Separate native audits cover2,048 continuous event/control cases and1,024 real3D aperture helper/HAL cases. No live job or GPU rendering. See private-3d-event.md and private-3d-aperture.md.

# Paired native SKSM register producers and scheduler links

Private implementation-derived AGX353.14/25G83 work. Offline Unicorn only; no
kernel/default changes, hardware access or submission. This is a reusable
preparation tool, not proof that the whole job is ready. No Apple executable
or instruction bytes are exported.

## Submission-route distinction

The hash-pinned native channel vtables resolve these register-list methods:

| Channel | Vtable address | Slot | Wrapper | Common producer |
| --- | --- | --- | --- | --- |
| G16_SKSM3D | 7eaa8e0, address point+10 | 228 | 89d5ce4 | 89df73c |
| G16_SKSM TA | 7eae018, address point+10 | 238 | 89e7aec | 89dd2c4 |

Both actual wrappers load the accelerator from channel10 and tail-branch to
the common producer. The new tool verifies the vtable target, wrapper body,
branch target and hash, then **executes the wrapper and full producer**.
Existing native SKSM submit instructions use these slots at895bbd8 for3D and
8a1f7b0 for TA. These are distinct from the SKU-channel microsequence callbacks:
G16 ordinary3D slot248->89d517c and TA slot250->89e7188. SKU submit calls the
stream callbacks; prior SKU stream evidence does not prove their use by SKSM.

Consequently the first SKSM candidate uses its matched register producers and
common scheduler records. It does not attach a SKU host stream merely because
we already have a working offline encoder. This does **not** yet establish the
firmware's complete internal scheduling/microsequence behavior or eliminate all
stream-related requirements from GPU initialization.

## New preparation tool

`prepare-native-sksm-registers.py` accepts saved descriptor/context/scene backing,
explicit TA and3D command GPU addresses, an explicit parameter-resource GPU map
and bit47 selection. It runs both native producers, checks every observed native
encoder call against the independent12-byte entry codec and verifies metadata
pointers/counts. It also compares the complete3D descriptor against the existing
independent metadata model and checks context/scene remain unchanged.

The tool replaces CPU-only lookup identities with separate emulator objects:
descriptor190 is the supplied100-byte context; descriptor918/1230 is the supplied
100-byte scene. Parameter-resource lookup/provider services use the explicit
parameter map. These CPU relocations are recorded and **are not live GPU
resource bindings**. Pointer shape and bytes alone do not qualify their identity.

Output includes a9c0-byte TA producer command region and2240-byte3D producer
region, corresponding to previously verified host strides. **These are register
producer outputs, not complete initialized channel commands.** Untouched command
fields are zero-filled and remain unqualified. Producer descriptors contain
emulator CPU identities and must not be copied into a live kernel context.

Optional explicit scheduler templates receive list addresses and **exported**
counts from the actual producer output. Caller-supplied replacement lists are
rejected. The tool encodes the existing common-work model, verifies its packed
pointer/count links, and exports the derived bindings. All other queue/event/
payload/QOS/mask inputs remain explicit. Queue accounting is a host fixture.
High pointer-prefix normalization remains unproved. Every receipt retains
`submission_ready=false`.

The baseline synthetic pair produces TA backing83/exported81;3D backing counts
91/16/23/10 and exported87/16/23/10. The conditional initial TA entry adds one.
Scheduler fields must use the exported count; silently using backing counts
would include producer tail records in the wrong scope.

## Input example

Paths are relative to the input manifest. Descriptor must be1800 bytes;
context and scene100 bytes each. Hexadecimal strings or integer numbers are
accepted for GPU bindings. Command addresses must be nonzero,64-byte aligned,
nonoverlapping and nonwrapping. Optional scheduler templates have the existing
`native_scheduler_candidate` schema with `register_lists` omitted.

```json
{
  "schema": "native-sksm-register-input-v1",
  "descriptor": "descriptor.bin",
  "context": "context.bin",
  "scene": "scene.bin",
  "ta_command_gpu": "0x100000000",
  "3d_command_gpu": "0x100010000",
  "parameter_gpu": "0x100020000",
  "gpu_bit47": false
}
```

```sh
python experiments/t6040-gpu/prepare-native-sksm-registers.py \
  /boot/GPUC003/private-apple/com.apple.AGXG16X input.json output-directory
python experiments/t6040-gpu/check-native-sksm-registers.py \
  /boot/GPUC003/private-apple/com.apple.AGXG16X /tmp/paired-registers.json
```

## Additional partial TA construction

Optional `ta_construction` now composes four checked TA SKSM construction
slice models over actual native register output. Separate caller context/stack
and explicit firmware translation inputs are described in
`2026-10-08-private-ta-command.md`. A separate partial command is exported;
producer-only files remain unchanged. Register backing/metadata60..77f stays
byte-identical. Intervening descriptor callbacks, completion binding and
conditional control were initially excluded; the newer continuous native audit
now executes the submitted-kick callback and derives control, including mode3.
The builder adds checked completion address arithmetic from an explicit mapping
return. Actual mapping/notification service semantics still remain fixtures.
Sixteen compositions and eleven malformed-input rejections pass. The command
remains submission-unready.

## Verification and remaining work

16 pairs pass through the verified native wrappers:80 register lists and80
producer-to-scheduler links,64 independently expected TA firmware-address
register values. Cases vary command/parameter/FW map addresses, conditional
initial entry and bit47. Six malformed inputs fail before output export:
boolean address, misalignment, overlap, address wrap, absent parameter map,
nonboolean feature flag. Source context/scene are explicitly zero fixtures;
these are not16 verified valid drawing jobs. The adjacent JSON records cases,
hashes and scope.

Next connect fully prepared descriptor/context/scene backing to this reusable
builder, complete SKSM channel fields and event/stamp/completion identity, then
implement Linux physical backing, mapping/cache visibility and queue publication.
Firmware retirement must precede coherent target readback or resource reuse.
The existing Apple9 shaders/target data can supply rendering inputs, but neither
a real triangle nor desktop acceleration has been proved.

The current failed warm INIT remains pinned on boot
fa78dd48-b214-46fc-8786-cae63897ad78. Normal reboot before live integration;
no forced unload/reset was attempted. Offline preparation can continue in Linux.

## Partial ordinary3D construction

Optional3d_construction now composes checked continuous ordinary header/resource/
body/tail fields over actual native four-list output. The payload byte derives
from incremented channel204, matching actual SKSM callback89d5cf0. Native
register backing and metadata are preserved. See private-3d-contiguous.md/JSON.
16 synthetic pairs and64 prepared-descriptor cases pass. Remaining event/control/
aperture/scheduling fields and live allocation/cache/completion are unqualified.
submission_ready=false.
