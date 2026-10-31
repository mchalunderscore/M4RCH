# Linux source record — linux-m4rch 7.3.0-28

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
