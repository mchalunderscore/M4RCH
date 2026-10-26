# Aurora J614s test profile

A separate bootloader/kernel test for the existing internal Arch ESP/root.
The prior `boot.bin`/GRUB pair is backed up and a new test `boot.bin` is staged.
Apple enrollment, stage 1 and the installed kernels are preserved. This is an experimental J614s port, not hardware qualification.

U-Boot embeds an Aurora board template and reconstructs its dynamic parts
from the **current** inherited FDT/ADT just before its EFI handoff. Its own
active NVMe control tree remains unchanged; Linux uses its stock EFI stub. A raw J616s DTB must
never be supplied to GRUB: its firmware addresses and OPPs belong to another
machine. The handoff refuses a different board. Unsupported firmware leaves the
GPU disabled and retains simpledrm. Internal speaker cards and amplifiers stay
disabled. Camera/AOP and DCP takeover require additional loader handoffs and
remain disabled when those handoffs are absent.

Generated sources, downloaded PR patches and build receipts live under ignored
`out/aurora-test/`. Build on a case-sensitive Linux filesystem (the Apple
container's `/work`), since Linux has case-colliding filenames on macOS.

The native ARM64 builder is Debian trixie-slim, image index
`sha256:62bd423aeee912639ca8ee681c2b762cb3e25137e0a92b20be455898a9f034ad`.
Kernel tools are Clang/LLVM 19, Rust 1.85.1, bindgen 0.71.1, dtc,
libelf/libssl development packages and standard make/bison/flex/bc tools.
U-Boot also needs swig, Python development headers and libgnutls development
headers. Mesa needs Meson 1.7, Ninja, LLVM/Clang/CLC 19 development libraries,
libllvmspirvlib-19-dev, libdrm, X11/XCB, Wayland, GLVND, udev, zstd, expat,
glslang and Python Mako/YAML/packaging/PLY/Jinja2/psutil. Exact installed
packages are retained in the build output receipt.

`rebuild.sh` records the final build commands. Its input trees are deliberately
explicit: `/work/linux` at `profile.json`'s integrated tree, `/work/mesa` at
the pinned tarball plus PR 55, and a **fresh** `/work/aurora-uboot` at
`profiles/gravity-loader.json`'s U-Boot revision plus that profile's checked
patch. Existing m1n1 and baseline DTB components come from the verified
`out/sdboot/gravity-loader/loader` build. The Linux integration applies the
locked PR patches in listed order. PR 408's GPU board append overlaps PR 406's
audio board append: retain both, with the GPU `gfx_mbox`, `gpu` and `pmp_gfx`
sections after the audio additions. Verify the resulting Git tree equals
`d570356031a315f307bdddb034e7f307dd6d2972` before building. No PR 413 changes
are included. `previous.config` is the AURA001 embedded configuration, whose
checksum is pinned in `profile.json`.

Validation includes an exact stock EFI-stub source comparison, ASan/UBSan
handoff fixtures (including malformed data and unsupported firmware), module
and initramfs readback, and loader framing checks. The Mesa Asahi offline
suite has 55 passes and one failure,
`NativeForms.ImageStoreUsesDataTypeAcrossChipsAndFormats`. Neither those
checks nor the synthetic supported-firmware fixture establish native GPU
operation. See `BOOT.md` for the hardware test and matched-pair rollback.
