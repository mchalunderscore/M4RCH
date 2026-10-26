# Native power v6 work in progress

Historical pre-reboot checkpoint: superseded by `POWER-V6-HANDOFF.md` after the
distinct source extraction, production stage and pure Rust qualification.
The frozen v6 handoff records current pins and the one root build command.

Saved 2026-10-11 before the manual reboot handoff. This is **not qualified,
staged, built, published or executed on hardware**. v5 and selected v21 remain
frozen. Root checkpoint at handoff: `6b2669777978db341a73265c5fc0e5b08fecde3f`.

The next coherent production component is native bundle child 4, with logical
size `0x6578`, CPU owner `+0x2d8`, mapping owner `+0x320`, and bundle offset
`0x5240`. These are already bound by the frozen v5 report; donor bundle-relative
power offsets must not be used.

Saved new files:

- `g16_t6040_power_v6.rs`, SHA256
  `39a521dd10bb1e96e109820a5f2d0954b3c19b1dd91123833002406bf8bc59b1`.
- `prepare_power_evidence.py`, SHA256
  `9709bf9a541fe7013d96e7b888c0b75834b3d77c72784792454a990858986ca0`.

The Rust API is `PowerData::from_adt(aic: Option<&[u8]>, ms:
Option<&[u8]>) -> Option<Self>`, with `period_aic_clocks` and `period_ms`,
`write_component` for the native power child, and `write_hardware_component`
for native hardware `0x2718` bytes. `POWER_COMPLETE` is false. The selected raw
property must be exactly four LE bytes. Zero periods and overflowing
millisecond multiplication reject. The writer preserves all unqualified bytes.

New source findings, from matched AGX host SHA256
`3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e`:

- Native `configureDevice` owner `+0xec88` gives AIC-clock property priority
  at `0x8967a60..0x8967b60`. Present `gpu-pwr-sample-period-aic-clks` stores
  clocks at `+0xedb0` and computes `+0xedac = floor(clocks / 24000)`, then skips
  `gpu-power-sample-period`. Otherwise the optional milliseconds property is
  used and clocks become `ms * 24000`. With both absent, the final result is
  **16 ms / 384000 clocks**. The initial literal pair is 16 / 400000 and must
  not be mistaken for the final absent-property policy.
- Captured original ADT has 200000 AIC clocks and 8 milliseconds; the selected
  native branch derives 8 from AIC clocks. ADT SHA256
  `01fb4c838a75aac89a3ddaa90996a65c394c07933a5b6927ec7ec13f6867cf39`.
  File: `out/gfx-native-fender-runtime-cycle/candidate/asc-graph-init/boot-f4a7b737-ed3d-4851-8fcd-cac56eb233d7/boot.adt`.
- G16X selected vtable `0x7eae398`, slot `0xf68`, binds getter
  `0x89e8b18` for `+0xedb0`; slot `0xf60` binds getter `0x89e8b2c` for
  `+0xedac`. Generic power store `0x89a86ac` writes clocks at power `+4/+8`.
  ARM hardware store `0x89cd1f8` writes milliseconds at hardware `+0xed8`.
- Generic power prefix `0x89a86cc..0x89a870c` supplies sixteen literal u32
  fields. ARM fixed array loop `0x89cadf0..0x89caf20` supplies zero
  `[0xbef,0x1bef)`, repeated LE u16 `0x7fff` `[0x1bef,0x1fef)`, and zero
  `[0x1fef,0x21ef)`. A one-off bounded Unicorn RAM inspection confirmed
  **5632 array bytes**; the saved extractor still needs its complete run.

The saved extractor independently pins eleven source spans, literal data,
vtable entries and original ADT; it is intended to execute native period
arithmetic, getters, literal stores and the array loop in RAM and emit
`out/gpu-gravity-normal-boot-v6-source-evidence/native-power.json`.
That report **does not exist yet**. Resume by running the extractor once,
repairing any diagnostic errors in this new v6 work, then pass the immutable
module/report pins to `gravity_boot_batch` for distinct v6 production wiring
and one pure Rust qualification. Root builds only after that handoff.

Essential unknown inputs remain: firmware CPU controller image `+0x980`,
size `0x160`, copied to power `+0xa0`; native uptime at power `+0x63d4`;
accelerator tuning/performance policy; preserved ARM owner fields
`+0x2888..0x28b8` and `+0x6530`; complete power producer; Linux mapping-policy
translation; and original ADT bridge installation. Captured nominal
`gpu-num-perf-states=15` must not be replaced by the eleven grouped hardware
rows. Do not fill these fields from donor defaults or open full power/bundle
startup gates.
