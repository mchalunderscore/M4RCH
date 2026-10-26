# Native revision 5

Return bundle: `out/aurora-direct/native-r5/return-20261024T112817Z`.
The exact successful kit, active boot.bin, GRUB configuration and staging
receipt are preserved beside it. `observation.json` records evidence hashes.

Linux brought up all 12 CPUs; online, present and possible are all `0-11`.
The topology shows four E cores and eight P cores, with frequency scaling.
NVMe root boot works. BCM4388 firmware initializes and registers `wld0`.
The owner confirms Wi-Fi and suspend/resume work; headphones were not tested.
The owner reports working webcam and USB3 on every port; those are owner tests,
not independent transfer-rate or frame-capture measurements in this bundle.

## GPU

The Asahi module loads and reads the GPU ID and fuse masks. It then rejects
the actual two-cluster, 16-enabled-core configuration (`0xf6fdb`). There is
no GPU render node; `card0` is simpledrm. This precedes Mesa initialization.

Pinned Aurora Linux `420a1c8f5492` explicitly admits only `(2, 20)` in
`drivers/gpu/drm/asahi/hw/t6040.rs`. The check is in `g17/mod.rs` before
firmware-manager construction. The configuration uses compute operand-state
register offsets and buffer sizes measured on the 20-core SKU, plus a measured
two-cluster render deflake layout. Changing the accepted count alone would
not establish that those layouts work on this fused 16-core SKU.

At inspection, `integration/aurora` still points to that pin. Draft PR 423
addresses submission and synchronization, retains layout selection, and
explicitly lacks T6040 hardware validation. It does not supply a qualified
16-core configuration. Existing local offline descriptor/storage audits are
not native 16-core render/compute buffer-layout measurements for this firmware.

Next GPU porting evidence: establish operand-state sizes/register offsets and
render deflake offsets for this SKU under the matching 25G83 firmware; compare
against the measured 20-core constants, add an explicit supported layout,
then qualify firmware startup, compute result readback and render readback
with the pinned private Mesa runtime before testing a desktop session.

## Remaining gaps

- No ALSA card registered. The headphone card defers while resolving its CPU
  DAI; the packaged `snd-soc-apple-mca` module was not loaded. Revision 6 adds
  that explicit load. Headphone operation remains pending a native test.
- The AOP node is disabled with handoff error `-4`; this bundle does not
  establish microphone, ambient-light sensor or lid-angle operation.
- AVD hardware video decode lacks `apple/avd-fw-v5-t1.bin` (`-2`).
- Camera/IIO collection used `find` without following class symlinks. Revision
  6 reads attributes through globbed class entries, and also collects USB
  sysfs attributes, platform driver bindings and available deferred-probe data.
- Headphone and other external audio still need explicit owner tests.
- Native DCP remains excluded for this firmware profile. A framebuffer desktop
  does not establish brightness control or external display takeover.

Built-in speaker nodes stay disabled and TAS2764/TAS2770 modules stay absent.
Revision 6 changes runtime/collection only; kernel and loader binaries match
the successful revision 5.
