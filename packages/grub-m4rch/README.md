# grub-m4rch

A complete AArch64 GRUB **2:2.16-1.1** package with the upstream ARM64
high-memory allocation fix. It provides versioned `grub`, replaces/conflicts
with the ordinary package, and retains the familiar GRUB tools and modules.
The `config-m4rch` boot hook generates the SD EFI application after upgrades;
GRUB installation does not change the internal loader or Apple's boot policy.

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

Inputs have SHA-256 pins, with archive/support-file BLAKE2 checks against the
pinned ALARM recipe. [source.json](source.json) records URLs, hashes, release
and fix commits. Pinned inputs do not promise identical package bytes across
different compiler or dependency versions. GRUB is GPL-3.0-or-later; copied
recipe/support-file grant scope remains unresolved as recorded in
[third-party attribution](../../THIRD_PARTY.md).

## Build and validate

The project builds this package through `make packages` or `make image`.
For the standalone recipe, use a disposable AArch64 Arch Linux ARM environment
with `base-devel` and its declared `makedepends`, then run as an ordinary user:

```sh
cd /path/to/packages/grub-m4rch
SOURCE_DATE_EPOCH=1790082997 PKGEXT=.pkg.tar.zst makepkg --syncdeps --cleanbuild
```

The recipe check generates an ARM64 EFI application from its built modules.
Executable allocator regressions cover high addresses; QEMU and native boot
remain separate checks. Installing GRUB updates the existing SD EFI binary
only when the project's hook completes successfully with the right ESP
mounted at `/boot`.
