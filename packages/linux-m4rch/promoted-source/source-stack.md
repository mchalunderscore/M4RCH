# Linux source record — linux-m4rch 7.3.0-30

The `7.3.0-m4rch-aurora1` kernel and the installer-assembled J614s stage 2 were booted on the target Mac after a fresh Aurora ALARM Minimal installation on 31 October 2026, as reported by the owner. Wi-Fi initially lacked BCM4388 C2 firmware; the owner reported success after provisioning the Mac's own Mriya firmware and rebuilding the initramfs. This is boot and Wi-Fi evidence, not complete peripheral, recovery or encryption qualification.

Release 30 retains those kernel and module bytes, preserves the package-owned initramfs configuration on upgrade, and includes locally provisioned Mriya firmware in subsequent initramfs builds when it is present. Release 30 has not been installed or booted; the installer used release 29.

The candidate rebuild used the same Aurora source commit and promoted patch series described below, with `CONFIG_SND_SEQUENCER=m`, `CONFIG_DM_INTEGRITY=m`, and `CONFIG_LOCALVERSION="-m4rch-aurora1"`. The kernel Image SHA-256 is `1ef76fe0a222fb9caa2c03efc63986a7c1c0209158519b9e6a793be92c78b071`, modules archive `10e02c338089df27008f9420e1a95f984b64c0ebf9354bbc321e2f3e79b38d5e`, config `80d5c60810efbd76d60e419e12c10465dd5b327ca97932f366bf62d49b11e4`, and unchanged J614s DTB `e2435554bfda78178d4427fc2645b8f024885048e1946ae74cd619094365efc8`. These inputs are retained locally under `cache/aurora1-promotion/linux-package/`. They are not tracked or published.

The following is the historical release-28 record.

Aurora Linux `23827fe87f4ffbabf5b7907a5907f9316286ce55`, archive SHA-256 `9bd85c8add7473dcab7f8306c3bf7ba21651f429d50d584d5c7337dffbb798e0`, with the ordered upstream-integration, mtp-handoff, touchid and jack patch series. The Touch ID changes add the J614s profile and default xART writes and first provisioning to off. The integration package explicitly enables guarded writes for the previously provisioned identity.

The `7.3.0-m4rch-touchid` Image and matching modules booted in the qualification trial on 31 October 2026. The user confirmed display, keyboard and trackpad operation; SEP restored the enrolled identity. The configuration differs from the previous trial in LOCALVERSION. Built with LLVM and Aurora corrected bindgen 0.73.2 (SHA-256 `2c0e9db67a20ce1a802d850c8820150a6df134e5371662d13119c58821cf0d00`).

Image SHA-256 `f66f222657422dbcbcc31162eec96f68fef382f6c2586b8860995762b9f0b791`; config `9420e2be2a500fe240e2cf8ec1e520ca55dd5b327ca97932f366bf62d49b11e4`; release-27 modules archive `6de87ff30ad8c0b716e7110d872e3ae0ba48b8a31756475a9cc53ab92266eeec`; DTB `e2435554bfda78178d4427fc2645b8f024885048e1946ae74cd619094365efc8`. The DTB was edited from the previously boot-tested binary to enable the SEP alias and sensor and set J614s firmware names; the retained DTS documents those changes but is not a byte-reproducible source for that binary.

Build inputs and logs are in `cache/touchid-candidate/` and `cache/touchid-promotion/`. The preceding source records are preserved in `cache/touchid-candidate/pre-touchid-package-sources.tar.gz`. This does not qualify suspend or all peripherals.

Release 28 incorporates the tested AOP audio module into the kernel package.
It applies Erik Bourget's [Aurora commit acdfd796](https://github.com/aurora-silicon/linux/commit/acdfd796a37d9ebcc3b7c50c42d6a4131f6a4a1c),
also carried by open [PR 437](https://github.com/aurora-silicon/linux/pull/437),
as the `jack` patch series. The common registration fix allows the jack when
`cout`/`cin` exist independently of `spkr`; J614s speaker DMA and amplifiers
remain disabled. On this machine the identical module was booted via the
temporary override: the owner confirmed stereo headset playback and clear
headset-microphone playback, and plug/unplug changed PipeWire routes correctly.
The sample's capture peak was low; repeated boots, sleep and longer use are
not yet qualified. See `experiments/jack/README.md`.

This is a module-only package refresh: the kernel Image, release, config,
DTB and every other module are unchanged. The new module has SHA-256
`d7dc1cd66cd0ccac8bd2497d85f74afcd223f5ffaa31b4384cbee0d5a7bce5bb`;
the reconstructed modules archive has SHA-256
`08e969d02fc54e74081fbd68e40220d595e8f97502495ec48e27082c2569341f`.
The archive builder compared all 389 entries with the retained release-27
archive and found only that module's contents changed. It is retained under
`cache/jack-promotion/inputs/`; original build inputs remain under
`cache/touchid-promotion/inputs/`. Source and build evidence for the module
are in `cache/jack-trial/`. This record does not claim a fresh full kernel
build or a boot after the package refresh.
