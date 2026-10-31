# Linux source record — linux-m4rch 7.3.0-26

The owner confirmed GRUB keyboard input and working Linux keyboard and
trackpad on the J614s handoff trial on 31 October 2026. Its boot log showed
retained MTP DART bypass, adoption of three RTKit buffers, and keyboard and
multi-touch readiness. This final Image and its modules were rebuilt from the
same source and configuration with LOCALVERSION changed to `-m4rch`. The
release is `7.3.0-m4rch`. See `docs/status.md` for final boot verification.

Source: Aurora Linux `23827fe87f4ffbabf5b7907a5907f9316286ce55`, source archive
SHA-256 `9bd85c8add7473dcab7f8306c3bf7ba21651f429d50d584d5c7337dffbb798e0`,
followed by the ordered `upstream-integration` and `mtp-handoff` series in
`patches/`. The J614s DTB is the previously boot-tested input, built from the
separately retained J614s DTS and its Aurora J616s base; it was not rebuilt with
this kernel. The baseline configuration was the installed 7.3.0-25 config,
with only LOCALVERSION changed. Full `LLVM=1` Image and modules build used the
Aurora corrected bindgen 0.73.2, SHA-256
`2c0e9db67a20ce1a802d850c8820150a6df134e5371662d13119c58821cf0d00`,
with Rust layout checks enabled. The build reported inherited NVMe and
Bluetooth thread-safety warnings and Rust deprecation warnings.

Image SHA-256: `6aee846f2c60a6362c86f241941444adcff984dbe4f3fdbc0762281430b25ec3`.
Config SHA-256: `6dc33a6b9d8083489f730832c66efcec0c06f86112b9451a558e66b6ff9bfc0c`.
Stripped module input archive SHA-256:
`dbbc0fb2506091c3f5991d0bb9e88059da0c26f3e65bf7f6664250465822d43b`.
DTB SHA-256: `5ef0aec63e8bb4b0deb9343f17de11dcc35a2c00815d1209cf283a69e87c42c6`.
The previous kernel's full historical source tree was not retained, so this
new source reconstruction cannot be claimed identical to it apart from the
handoff. GPU, suspend and other peripherals are not comprehensively qualified
by the keyboard test.

Machine-local source archive, generator, build logs, previous boot pair and the
pre-promotion working-tree archive are in `cache/mtp-promotion/`; see
`docs/recovery.md`. Previous binary package archives and their historical source
records remain in `cache/installed-20261031/` and the pre-promotion archive.
