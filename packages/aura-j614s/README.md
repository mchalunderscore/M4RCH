# Aurora Aura candidate for J614s

On 1 November 2026 the installed candidate's stage-two payload was combined
with the DTB and compressed U-Boot from the booted stage-two bundle and armed
for the next boot. The assembled SHA-256 is
`7faa2fa33f05f4020e3bb1bd39af3100ca6bffa3812c1f23dcb77e2960af85bd`.
The previous loader was verified and copied to the EFI partition and Linux
root. On the next boot (ID `85e1936e-09d7-43c4-b209-cc3631ac600a`), Linux
reported Aura stage two `1.0.0b1`; the owner observed the Aurora logo and
confirmed Touch ID. The internal display, Wi-Fi, root storage and fingerprint
identity were present. This selection persists; failure does not revert
automatically. See `docs/recovery.md` for recovery. Aura stage one has not
been installed or booted. The owner subsequently confirmed an external
display worked on this boot; the kernel logged HDMI connection and
disconnection. USB-C display output and other peripherals remain unqualified.

The identical booted stage-two bundle was subsequently promoted in
`aura-j614s-boot 20261101-3`, which owns the EFI path and pins the component
packages. Regenerated GRUB is byte-for-byte identical to that used for the
successful boot. The package's FAT-aware metadata passes `pacman -Qkk`.

[`stage-aurora-aura.py`](../tools/stage-aurora-aura.py) overlays the retained
J614s m1n1 behavior series on Aurora ALARM commit
`2d2555ecc578d6f40fa738c9c5b4e639f116a3cf`, Aura source
`a9cad94edb46fd4baf77c6cb1776b3bb5f1a566f`. It verifies the recipe, support
files, source archive and patch hashes, preserves Aurora's build and packaging
functions, and records the overlay in the package. The archive and recipe
inputs are retained under `cache/aura-recipe-input/` and
`cache/aura-j614s-staged/`.

The staging recipe no longer carries the host-only GPU calibration test;
the original change remains in the compressed promoted-source provenance.
This is a recipe change and has not changed the installed loader.

Aurora describes Aura as a fork of m1n1 aurora-wip in [PR 16](https://github.com/aurora-silicon/aura/pull/16),
which reports a J616s stage-one and stage-two test of an earlier baseline, not
J614s qualification of this package. [PR 15](https://github.com/aurora-silicon/aura/pull/15)
remained open when checked; its M4+ reservation was reported in PR 16's
platform batch. [PR 34](https://github.com/aurora-silicon/aura/pull/34) remains
an unqualified T604x SIO draft, and [PR 37](https://github.com/aurora-silicon/aura/pull/37)
merged an M4 Pro ANE preload handoff after the source pin; it was not tested
on hardware at merge. These do not establish equivalence to the booted J614s
loader. Review upstream and package source again on every update.

The J614s DAPF candidate in [`01-dapf-corrected.patch`](01-dapf-corrected.patch)
requires typed AOP/ISP bank metadata and cleans up power on validation failure.
A trial boot reported both banks ready, AOP ready and the ISP driver bound;
image capture and the standalone upstream handoff remain unqualified. The
next package recipe includes that tested source and retains the original in
`cache/aura-j614s-staged/` for provenance.

The original patches apply with zero fuzz, some at offsets. The local
[`05-sd-power.patch`](05-sd-power.patch) retains the J614s SD-reader
power action while adapting its context to Aura's current `kboot.c`. A trial
boot without the former extra PMP tree-space allowance initialized PMP and the
display; the staging recipe therefore no longer carries that allowance. The SD action still fails the boot if its
board-specific validation or write fails. This is source adaptation, not a
proof of equivalent hardware behavior. The package includes both stage-one
artifacts and a stage-two payload; stage one has not been installed or enrolled.

The native Aurora-recipe build completed for both outputs with Rust 1.99.0
and LLVM 23. The unsigned candidate is
`cache/aura-j614s-staged/aura-1.0.0b1.r20261101-2.1-aarch64.pkg.tar.xz`
(SHA-256 `173702da166ec499216d66937164dc7ef7f3763b433b9f067666d06970d7edca`).
The packaged stage-two SHA-256 is
`25660ee854c384c5395f0c81adec030bf0c3adcb5ecde97cdf64671ab5815026`;
the stage-one raw SHA-256 is
`5f1fb13b67ae4858d7613c4e894679d379a45004b35b249d1cf09a3b99d62378`.
They match their build outputs. The initial packaging logged a fakeroot payload warning while the isolated LLVM
library path was active. Repackaging the same build with the host packaging
environment completed without that warning; all payload paths, types, modes,
ownership, links and regular-file hashes matched the first archive. Audit the
package and its installation hooks before subsequent updates. Stage two has
booted as described above; SD, external display, extended GPU, memory and
other handoffs remain unqualified.
