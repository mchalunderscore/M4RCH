# Packages

`make kernel` compiles the pinned, patched kernel. `make packages` wraps its
verified output and configuration with unprivileged `makepkg`, then validates
them in a disposable Arch root. Generated recipes, recipe archives, packages
and hashes are recorded under `out/sdboot/packages/` and
`out/sdboot/custom-packages-manifest.json`.

| Package | Owns |
| --- | --- |
| `linux-m4rch` | Kernel, matching modules, driver blocklist, mkinitcpio preset and build provenance |
| `config-m4rch` | Services, desktop policy, firmware, diagnostics, SD overlay, initramfs and pacman boot hooks |
| `grub-m4rch` | AArch64 GRUB with the upstream high-memory allocation fix; provides/replaces `grub` |
| `paru-m4rch` | Pinned AUR helper; installs the ordinary `paru` command |

The package artifact is `linux-m4rch-7.1.3`; the kernel and module release is
`7.1.3-m4rch`, retaining the numeric prefix required by mkinitcpio. Source and
patch hashes remain in its build provenance. Compatibility declarations allow
migration from the previous package names. `/etc/arch-m4/boot.conf` holds each
installation's boot identity; the update installer preserves it with pacman's
`NoUpgrade` before starting the transaction.

Account creation, hostname, fstab, machine identity and initial home preferences
remain installation state. Kernel/modules and policy are package-owned;
the initramfs does not install modules into the persistent root.

## Install an update

Copy the generated kit to the mounted SD ESP and use its exact printed path:

```sh
sudo sh /boot/update-ID/install.sh
```

Use the kit for custom package updates and migration; direct `pacman -U`
does not preserve the old package's boot identity. The kit verifies checksums,
checks the mounted root and ESP, preserves the configuration, and installs its
exact package set in one pacman transaction. Repository signatures remain required; explicit local packages
use `LocalFileSigLevel = Optional`. The configuration package contains
extracted firmware and remains a local artifact rather than a public binary
release. See [setup](../docs/setup.md#update-linux-without-enrollment).

Boot hooks check `/boot`, rebuild the matching initramfs and publish the kernel,
SD overlay and GRUB there. They replace the standard mkinitcpio install/remove
hooks so one writer owns this sequence. `depmod` generates unowned dependency
indexes as usual. If a hook fails, resolve its error and retry:

```sh
sudo m4rch-boot-update
```

Do not remove the card or reboot during a transaction: promotion on FAT is not
an atomic multi-file operation. Reinstall the matching kernel/configuration
versions together for rollback.

## paru and GRUB

Run `paru` as Alice, for example `paru -S package-name`; it builds as the user
and requests sudo for installation. Git, `base-devel` and Rust are included.
[The pinned source](paru-m4rch/source.json) uses libalpm 16, matching pacman 7.1.
The builder compiles against that installed library and runs the result before
publishing its package.

[GRUB's recipe notes](grub-m4rch/README.md) document its allocator fix and source
pins. Upstream and copied files retain their own licensing scope, including
an unresolved grant for copied ALARM recipe/support files; see
[third-party attribution](../THIRD_PARTY.md).
