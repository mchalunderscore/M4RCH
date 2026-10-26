# Native power v6 root build handoff

2026-10-11: the distinct v6 stage, pure Rust qualification and root module
build/link are complete. Root's single saved make result returned zero with
all 70 immutable source inputs unchanged. No install, load, GPU publication,
hardware action or kernel rebuild occurred. All Q-bound files are frozen. The earlier
`POWER-V6-WIP.md` is historical and is superseded by this handoff.

Root used this one build command from the repository root; do not rerun it:

```sh
python3 experiments/t6040-gpu/desktop-integration/t6040-native-boot/build_module_v6.py out/gpu-gravity-normal-boot-v6
```

The builder validates qualified inputs and the 70 immutable staged source
files before make, then saves make's terminal result before postchecks. It
never loads the module or rebuilds the kernel. Observe existing intent/log/
result files if a build is interrupted; do not restart the same attempt.

Frozen receipts:

- `out/gpu-gravity-normal-boot-v6/qualification-v1/qualification.json`, SHA256
  `705aed72879c49f2058a1806fe97f0c0d23a0f33c009928fc91d6093ec0dbd5b`.
- `out/gpu-gravity-normal-boot-v6/stage-receipt.json`, SHA256
  `d23243bffe8be52c98312394ec3bf3fae78049cfb078838ecc6be1153d4f28fb`.
- `out/gpu-gravity-normal-boot-v6-source-evidence/native-power.json`, SHA256
  `df3411781630ef92d84c37d50c40ca2d243d63be928993cc77994e401a13d1bd`.
- `build_module_v6.py`, SHA256
  `d25fedb95e74dc1ac0dc72c29a88087eca50bf24c87189040a86748c7c6333d0`.

The actual Platform constructor now selects native AIC-first raw ADT timing.
Captured 200000 clocks derives 8 ms; AIC success skips the millisecond query.
The native fallback is 16 ms / 384000 clocks. The actual bundle producer writes
the selected prefix and ARM fixed initializer into child4 (`0x5240`, logical
`0x6578`), and milliseconds into native hardware `+0xed8`. No donor power
offsets or controller defaults are selected.

The saved-source extractor passed 48 native arithmetic cases and proved 5704
selected power bytes, including the 5632-byte fixed ARM array initializer.
Rust compile/run both returned zero with no warnings. Actual constructor and
bundle methods were exercised against original captured performance bytes and
observed topology; complete power/hardware/bundle buffers of 25976 / 10008 /
147456 bytes were compared independently. Tests covered priority, ignored
secondary-property errors, fallback/defaults, malformed/zero/overflow input,
error propagation, short buffers, unknown-field preservation and closed gates.
The frozen v5 expected bundle was reused; its broad audits were not rerun.

`POWER_COMPLETE`, `BUNDLE_COMPLETE`, Region C completion and normal startup
remain false. Native controller image, uptime, tuning/performance-count policy,
ARM preserved owner fields, complete power, original ADT bridge and Linux
mapping-policy translation remain required inputs. Captured nominal state
count 15 is recorded and is not replaced by the eleven grouped hardware rows.
Max-power/revision and unused first reg words in the test adapter remain
explicit fixtures without new producer qualification.

Root's completed module is `out/gpu-gravity-normal-boot-v6/build-owner/asahi_m4.ko`,
406104 bytes, SHA256
`43063e7a80a4a8861dca849d4a2337e98508bc9d929fc2662f8302461ef2be2e`.
The saved make result SHA256 is
`81b194ad0b92e95a5582e4a8c7f90eb100d21fb05ee4cc3e67a16a57d3cea1e0`.
`module-build-closure.json` confirms make returned zero, the full module linked,
and all 70 source inputs were unchanged. The tracked integration report
`docs/evidence/2026-10-11-gravity-native-t6040-components-v6.json` now records
those terminal build/log/module pins. Report and handoff are not Q inputs;
no qualification, staged source, v5 or execution-trial file was changed.
