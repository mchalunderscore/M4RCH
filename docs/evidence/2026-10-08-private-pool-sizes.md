# Native firmware pool element sizes resolved

Private-derived matched AGX353.14 / Apple25G83, no hardware execution.
The earlier runtime-stride provenance gap is resolved by the native
AGXFirmware::configurePoolElementSizes function at 0xfffffe00089a2a78.

## Native dispatch and size values

Both AGXFirmware and AGXArmFirmwareASC vtables bind slot8a0 to this same
function. The initFirmwareData caller at89ab0b0..89ab0e0 invokes that virtual
slot, executes the complete native size initializer, then copies field218 to
TA pool stride12f8. These operations execute together in the checker.

| Firmware source field | Native size | Qualified role |
| --- | --- | --- |
| 218 | 9c0 | TA pool stride copied to12f8 |
| 220 | 2240 | ordinary3D stride copied to1338 |
| 228 | a00 | FastBlit stride copied to1378 |
| 230 | 1040 | CL stride copied to13b8 |
| 270 | 40 | AddFinalFrgGTPCKick stride copied to1538 |
| 278 | 40 | KSMKickQueueAddKicks stride copied to1578 |
| 288 | 40 | KSMKickQueueEntrySignal stride copied to15f8 |

All values are hexadecimal bytes. Other initializer writes are recorded in
JSON without assigning unsupported semantic labels. Six downstream source-to-
stride copy pairs execute natively after the initializer and match full fixture
models. No external provider is needed for this function; vector constants are
read from the original matched binary.

## Comparison with supplied writeup

The ordinary fragment2240 and compute1040 sizes match the uploaded document and
now have direct native host allocation-stride provenance. The native TA pool
stride9c0 is32 bytes larger than the document's9a0 record extent. Allocation
padding could explain this; native stride alone does not prove the document's
wire-payload extent is wrong. Preserve this distinction when implementing pools.

Likewise all three post-kick pool strides are40, while the writeup specifies an
18-byte-hex opcode14 wire record. The preceding audit's21-byte-decimal patch
fits both extents. A40-byte host slot does not establish a40-byte wire message.
FastBlit stridea00 is separate from ordinary3D and is not covered by that spec.

## Verification

```
python experiments/t6040-gpu/audit-private-pool-sizes.py \
  /boot/GPUC003/private-apple/com.apple.AGXG16X \
  docs/evidence/2026-10-08-private-pool-sizes.json
```

128 randomized prefilled firmware objects pass. An explicit independent table
compares all native constant initializer writes, including preserved gaps, then
compares six downstream stride copies. Native virtual caller, function/vector
constant loads and return execute in Unicorn RAM. Both actual vtable targets,
function/caller/copy hashes and binary hash are pinned. PAC is bypassed for the
synthetic caller vtable. This proves the reviewed host size initialization and
copies, not allocation/cache policy, concurrent operation or GPU acceptance.

## Implementation consequence

Use established host strides2240/a00/1040 for ordinary3D/FastBlit/CL pools and
40 for these three control pools; keep encoded payload length separate. Earlier
pool request and backing-rounding audits can now use these real native constants
rather than infer from record tails. Full native TA construction, release and
real render-state/shader/target preparation still require work. No live draw is
proved; retained warm INIT still needs normal reboot before hardware testing.
