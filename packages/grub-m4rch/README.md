# grub-m4rch

The AArch64 GRUB **2:2.16-1.2** recipe carries the upstream ARM64
high-memory allocation fix and a package-local license. The currently installed
package remains `2:2.16-1.1`; this recipe has not yet been built or installed. It provides versioned `grub`, replaces/conflicts
with the ordinary package, and retains the familiar GRUB tools and modules.
The formerly used `config-m4rch` SD boot hook was retired. The current
internal boot chain and recovery procedure are documented in the
[recovery guide](../../docs/recovery.md).

## Allocation fix

GRUB 2.16 limited ARM64 allocations to 4 GiB, below Apple Silicon's RAM.
[Neal Gompa's upstream revert, 711110da](https://gitlab.freedesktop.org/gnu-grub/grub/-/commit/711110daccaf15df695b270d13f76b5bc84a64dd),
applied unchanged without fuzz, restores
`GRUB_EFI_MAX_USABLE_ADDRESS` to `0xffffffffffffULL`.

The recipe derives from
[ALARM core/grub at c1c4c53a](https://github.com/archlinuxarm/PKGBUILDs/tree/c1c4c53a48ac05adcda9539a10e2466b891e3ee7/core/grub).
It retains distribution patches, defaults, install script, SBAT, dependencies
and AArch64 flags. Local changes include the `grub-m4rch` package identity,
higher release, allocator fix, provenance and use of the official release
archive. Generated configure/gnulib files already exist in that archive;
font-path adjustments apply directly to generated `configure`.
The pinned ALARM `sbat.csv` and the installed package both contain a malformed
GNU project URL; the source is retained unchanged from ALARM.

Inputs have SHA-256 pins, with archive/support-file BLAKE2 checks against the
pinned ALARM recipe. [source.json](source.json) records URLs, hashes, release
and fix commits. Pinned inputs do not promise identical package bytes across
different compiler or dependency versions. GRUB is GPL-3.0-or-later; its license is retained in `COPYING` and installed
with the package. The ALARM recipe records maintainers Christian Hesse, Tobias
Powalowski, Kevin Mihelich and Vasily Khoruzhick, plus contributors Ronald van
Haren and Keshav Amburay. No explicit recipe-level grant was found in the
pinned ALARM root or contribution notes; the package license field alone does
not establish a grant for copied recipe/support files. Preserve those notices
and resolve their scope before making a publication-clearance claim.

## Build and validate

This recipe is not yet integrated into the current four-package native build
workflow. For the standalone recipe, use a disposable AArch64 Arch Linux ARM environment
with `base-devel` and its declared `makedepends`, then run as an ordinary user:

```sh
cd /path/to/packages/grub-m4rch
SOURCE_DATE_EPOCH=1790082997 PKGEXT=.pkg.tar.zst makepkg --syncdeps --cleanbuild
```

The recipe check verifies the address constant and generates an ARM64 EFI
application from its built modules. It does not exercise high-address
allocations, QEMU or native boot. The earlier SD EFI update hook is not part of
the current workflow. Verify the installed GRUB and boot configuration before
any update.
