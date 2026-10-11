# Current joined v8 checkpoint — complete power integrated and compiled

This section supersedes the v7/historical handoffs below. Complete Rust power,
hardware power fields, Region C and AON outputs match actual native ARM routines
for identity16 and grouped11 test maps. Raw ADT CPU voltage initialization and
mapped copies execute original instructions. The raw millisecond provider is
ACC+edac, distinct from AIC clocks at edb0; two GPU clusters enable native tags.
Disabled primary voltage terminates the table, now fixed in the Rust writer.

Distinct out/gpu-gravity-normal-boot-v8 compiles/links its actual module with
75 unchanged input files, zero errors/42 warnings. It integrates the one future
cold performance-map snapshot, explicit 20W/raw24MHz policy, owned QoS/AON/
support aliases and native hardware timestamp+28. POWER_COMPLETE=true for
this qualified experimental writer. BUNDLE_COMPLETE remains false; no loading
or installation occurred. This is not READY; do not ask for a reboot yet.

Remaining concrete work: native TA/3D Work/dependency producers (the normal
runtime still uses donor render records), firmware loader reservations/UAT
root, and bounded combined live launch/capture. Boot14343 remains consumed;
no GPU access or failed wake replay. User manually reboots only once READY.

Evidence docs/evidence/2026-10-11-gravity-native-t6040-joined-v8-progress.json
and docs/evidence/2026-10-11-gravity-native-t6040-complete-power-v8.json.

## Prior v7 checkpoint (superseded)

# Current joined v7 checkpoint — compiled, not a triangle candidate

This section supersedes the historical handoff below. Root generated
`out/gpu-gravity-normal-boot-v7`, passed the new joined queue-owner checks,
and compiled/linked the actual module: 75 source inputs unchanged, zero
compiler errors, 42 warnings. The module is not installed or loaded.
Startup still refuses the incomplete native power/bundle path. This is not READY.

The joined source selects native RAM channels, persistent queue/QoS owners,
config15 before first Work, and native control admission before any public
submission. Native shutdown retains storage pending GPU OFF retirement.
The donor bootstrap Work injection is excluded from native startup.

The full Apple ARM setup and power routines now return in offline RAM with
explicit 20W/time/absent-AON/zero-leakage fixtures. The complete Rust draft
has not yet been compared with those full outputs, and remains gated. Bind
actual performance/voltage providers and native timestamp/owned GPU aliases
before extending the experimental startup. Keep boot14343 consumed; no GPU
access, replay, installation or reboot request on that boot.

Evidence: `docs/evidence/2026-10-11-gravity-native-t6040-joined-v7-progress.json`.
Subagents stopped on a reported usage limit. Their saved files are retained;
root is continuing the combined implementation.

## Historical handoff

# Native normal boot v7 integration handoff

Root assigned one coherent native boot/graphics integration batch, deriving from
the frozen, compiled v6 source at `out/gpu-gravity-normal-boot-v6`. Selected v22
and all prior stages remain frozen. No v7 stage, qualification, module build,
installation or hardware operation has run.

`gravity_boot_batch` owns new `stage_v7.py`, `qualify_v7.py`,
`build_module_v7.py`, actual production/runtime selection and original ADT input
closure. `dynamic_runtime` owns new `g16_t6040_power_v7.rs` and its complete
native power/controller/performance source report. `runtime_host` owns new
`g16_t6040_shared_v7.rs` and native Root/RegionA/status/header/channel/shared and
Region C ownership closure. Those agent interfaces are still under research;
do not stage or open a gate until the required dynamic fields are accounted for.

New `native_adt_bridge_v7.py` implements an actual offline FDT transformation:
all original SGX ADT properties become exact raw `apple,sgx-` byte aliases;
stale aliases are deleted so absent native defaults stay absent. It verifies
every unrelated FDT property is preserved. It does not provide core masks,
revision, maximum power, resource ownership or a live bootloader hook.
The helper has only been imported to inspect saved FDT semantic contents;
its full bridge qualification is pending an actual native GPU node.

Root saved authoritative inputs in `out/gpu-gravity-native-boot-v7-inputs`:
`firmware-flat.dtb` SHA256
`55a125457e7bd416c40a934f47b021c2eb6ec3ef7ed8753af8a85780cbd66e50`,
`kernel-live-of.dtb` SHA256
`1ef2af361eecd0a27adb7af078d5dee89814dff549233aff909d98a28b172eed`,
with `receipt.json` provenance. The saved kernel OF export has 424 nodes and
no GPU/agx compatible node. It cannot yet be fed to the native driver's input
bridge without an explicitly prepared native GPU description.

Required production fixes discovered:

- `g16.rs` selects native Main at root+18, but publication and
  `g16_runtime.rs` still reconstruct `MainConfig::bootstrap(BUNDLE_ADDRESS)`
  donor channels for admission, flush, retirement, stamps and trace controls.
  Store and consume one selected native channel topology consistently.
- `g16.rs` work-cursor external maps use donor physical addresses
  `0x300d60000/0x300d64000`; native maps need selected SGX physical base and
  native cursor owners. Host-MMIO offset derivation must agree with that topology.
- The native power path still requires artificial `apple,m4-max-power-mw`.
  Dynamic agent resolved native accelerator+f2a0 → firmware bd8/bdc →
  Region C+84; use its source-backed initializer/property selection.
- The current normal opening barrier uses donor `g16_queue::Queue`0xb0 and
  moved fields. G16S0xc0 queue/control/Work ownership must be integrated before
  graphics startup is considered complete, even if root/bundle bytes qualify.
- Native full hardware mappings retain explicit Linux PTE transfer uncertainty;
  source-bound zeroed reserved/optional bytes need not remain permanently unknown.

Root requested a pause in v7 work for urgent class-1 power assertion integration.
Resume from these saved files and agents' bounded source reports. No previous
broad qualifications or builds need repetition.
