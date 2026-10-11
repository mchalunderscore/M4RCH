# Native power v7 component handoff

The new typed power component is complete for its stated scope and ready for
normal v7 production integration. Full native power and normal startup remain
closed. No hardware operation, module installation, kernel rebuild or frozen
v6/v23 edit occurred.

Use `g16_t6040_power_v7.rs`, SHA256
`554a4d9f92e6f8cc5b57b7c264066d06b4adaabf9d5cf67a00617c1c84be7c30`.
Its actual Rust methods matched the saved native producer in
`out/gpu-gravity-native-power-v7-qualification-v5/qualification.json`, SHA256
`7f2bd5cb31a2121297d816ae64b8f421980511b275a8ac0428821125c2aeb4d6`.
The numeric source report is
`docs/evidence/2026-10-11-gravity-native-power-v7.json`. Failed earlier
qualification adapters and the narrower v2 result remain historical; v5 is
the authoritative completed qualification. Do not repeat old v6 broad audits.

The qualification executes saved unmodified G16X controller configuration,
SRAM scaling, generic `setupConfig`, generic full `0x6578` power clear, and the
ARM capture/restore/fixed-array prefix through `0x89caf20`. It compares actual
Rust whole power (25992 bytes including the untouched 16-byte guard), hardware
(10024 bytes including guard), and Region C `+84/+88/+8c` outputs against the
native RAM result. Four cases vary maximum power, native ticks and preserved
owner bytes; one also overrides 18 optional raw tuning properties. Duplicate,
malformed, zero-filter/base, excessive-deadzone, invalid maximum and short
buffer refusals are checked. Rust compile/run returned zero, with empty
stderr. Frozen v6 timing/ARM fixed-array evidence is composed as an existing
source binding; the new native lifecycle execution checks its integration.

`PowerData::from_adt(&[(&str, &[u8])])` accepts original SGX property bytes.
Required keys are `perf-state-count`, `perf-state-table-count` and `perf-states`;
the selected table has 16 rows and two clusters. Optional keys are listed in
`OPTIONAL_WORD_PROPERTIES`. The nominal 15 is the maximum row index, independent
of the eleven grouped voltage rows. AIC timing takes priority; absent inputs
select the source default. No artificial `apple,m4-max-power-mw` is consumed.

The actual producer methods are `write_component` for child4,
`write_hardware_component` for child0,
`write_secondary_hardware_component` for independently supplied native CPU
`+19f20` frequencies, and `write_region_c_component` for its three power fields.
`LifecycleProviders::capture(owned_power, calculated_maximum_mw, native_ticks)`
captures `6530..6538` and `2888..28b8` before the generic clear.
`write_lifecycle_component` restores them afterward and stores native ticks at
`63d4`. The controller image uses the selected fresh zero CPU allocation and
native sixteen-entry 1.02 SRAM scale. This is not a producer for an arbitrary
reused native CPU controller image.

Maximum power remains an actual G16X provider requirement: its native final
calculation consumes chip leakage from the `0x508374000` fuse mapping, per
cluster voltages/frequencies and topology. Optional `gpu-device-max-power` /
`gpu-max-power` are intermediate values overwritten by that calculation.
Final accelerator `+f2a0` initializes firmware `+bd8/+bdc`, then Region C `+84`.
The qualification's maximums, ticks, secondary frequencies, chip class 28 and
external OSData/time/lock/power services are explicit RAM fixtures. They do not
qualify these hardware providers.

Remaining complete-power requirements are the actual calculated maximum,
native absolute-time domain, secondary-frequency owner, and ARM controller
override/tails after `89caf20`. `POWER_COMPLETE` remains false. The production
integration should use the provider-independent component immediately and
expose the typed lifecycle only when genuine owned providers are available.
Do not select fabricated maximums or Linux nanoseconds to open startup.
