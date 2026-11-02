# Aurora kernel candidate for J614s

**Historical candidate:** Aurora Linux PR #795 was merged as
`dc87ceeea59f7b1075fd5e7659869dc12dd16ca9` on 2 November 2026. Its J614s
device tree and SEP profile replace the old local board and SEP patches. The
old stager targets a kernel from before that merge and is retired. Its inputs,
including the superseded draft board patch, are preserved under
`cache/pr795-merged-cleanup-20261102/`. The installed PR-stack snapshot is
described in [upstream-pr-stack](../upstream-pr-stack/README.md); it has not
automatically been rebuilt from the merged commit.

The following is the historical record of an earlier candidate. This
directory held additions to Aurora ALARM's proposed kernel recipe. The
9.4 kernel used Aurora's SEP defaults and was promoted as the default at the
time. Its kernel and modules were booted through a one-boot entry. The former
The retired kernel stager verified ALARM PR 83 commit `2d2555ecc578d6f40fa738c9c5b4e639f116a3cf`, the
kernel archive at `f41ac3de3e645232524ef28c8347d7d37f16bf23`, and each patch.
It kept Aurora's build and package functions and appended ordered patches to
Aurora's `source` array. That candidate used `pkgrel=9.4` and kept
Aurora's defaults for xART writes and keybag provisioning. The previous 9.3
kernel retained the local defaults. Use only a new output directory:

The 9.4 candidate booted on 2 November 2026 as
`31ca2122-f611-43cf-881e-b50b782b2752`; the owner confirmed Touch ID worked.
Its source differs in `sep.rs` only in the two requested defaults. The
package-managed kernel and headers were then installed, the initramfs checked
and GRUB regenerated with one default entry. The trial and normal kernel
images have identical hashes, but the regenerated normal boot configuration
has not yet been booted. The previous kernel, headers, modules and boot
files are preserved under `/var/lib/m4rch/j614s-sep-defaults-promotion-20261102/`.

The recipe and verified source archive used on 1 November 2026 are also held
in the ignored machine-local `cache/linux-aurora-f41-candidate/` directory.

The default stages the 9.4 recipe with the internal-display opt-out and the
J614s DISPEXT1 power-domain links. The previous 9.3 version booted with both
display stages and both external display processors enabled, and the owner
confirmed an external display worked on the promoted stack. The
previous kernel and packages are archived for recovery. See the
[integration notes](../../docs/aurora-package-integration.md) for the live-tree
mismatch, upstream context and recorded evidence.

The first J614s GPU admission patch and the MTP, SEP and jack patches come
from the recorded booted M4RCH stack. The old local GPU deferred-close patch
did not apply to Aurora's newer `exec_lock_vm` API ([Aurora PR 521](https://github.com/aurora-silicon/linux/pull/521)).
Instead this candidate carries the four patch emails from closed, unmerged
[Aurora PR 772](https://github.com/aurora-silicon/linux/pull/772), which
implements a sequence-based deferred-close fix. Its source-level validation
and upstream test report do not establish equivalence to our old fix or
qualify this J614s. This local carry is needed because the proposed PR is not
part of the pinned package source. All four emails and remaining local patches
applied against the real pin with fuzz disabled; some hunks moved by offsets.
The full patch's SHA-256 is
`83ca2c0495d9b5c98537d8cfb972ce040129b2f527c59debd1b4ef681d3044a8`.

The now-archived `j614s-dtb.patch` packaged the retained draft DTS and Makefile entry. It
compiled against the pinned source with the kernel's arm64 device-tree build.
The result differs materially from the DTB in the booted stage 2: upstream's
J616s parent tree has changed and the prior binary was edited separately.
Do not substitute the newly compiled DTB without resolving those changes and
the loader handoff contract on this specific Mac.

`makepkg --verifysource --nodeps` passed for the staged recipe. An actual
`makepkg --nobuild --nodeps` preparation applied all patches successfully,
then initially stopped because `rustup` was not installed. The dependencies
were subsequently fetched as signature-verified Arch Linux ARM packages into
an isolated project cache, and Rust `1.99.0` was installed there. An actual
native package build completed on 1 November 2026 and produced:

- `linux-aurora 7.3.0.aurora1-9.1`, SHA-256
  `f86f5c748f863167640ea135363205597df78f738f4007c710cf3e820905c189`;
- `linux-aurora-headers 7.3.0.aurora1-9.1`, SHA-256
  `a28d855f8a4c06bc532063ff4d9c0bbf4f9db66f085a56051c2b81f00a4e1caa`.

Those earlier packages are in `cache/linux-aurora-f41-candidate/`. They contain the
J614s DTB, the `aurora` GPU module and `apple-sep` module. The build warned
that four header-package binaries contain references to the source directory;
this has not been evaluated for external module builds. The booted and
promoted 9.3 artifacts and their source provenance are in
`cache/linux-aurora-power-diagnostic/`. The built DTB differs from the boot
loader's DTB as described above.
