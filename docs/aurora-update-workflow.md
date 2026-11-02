# Updating the Aurora forks

The [Aurora ALARM fork](https://github.com/mchalunderscore/alarm-aurora/tree/j614s/full)
pins the J614s source forks. Its packages were built with `makepkg -si`; the
forked boot stack booted successfully in a one-shot trial on 2 November 2026; the forked kernel is now the persistent GRUB default. See
[status](status.md) and [recovery](recovery.md).

Before an update, review current Aurora source, recipes, relevant pull requests,
discussions and follow-ups, and remove local commits that upstream has adopted.
Rebase each component's `j614s/full` onto the source used by Aurora's package,
retaining the individual PR commits, and update the forked PKGBUILD pin. Build
and install the relevant recipes on AArch64 with `makepkg -si`; review split
packages and their dependencies. Local builds are unsigned. Host Mesa, FEX
and Flatpak releases need compatible versions; the patched FEX guest has not
been built on this machine.

The standard `update-m1n1` hook is enabled with its normal DTB selection. It
assembles Aura, the installed kernel's DTBs and U-Boot into EFI stage two.
The updater selects the highest-sorted `*-ARCH` modules directory; check that
it belongs to the intended kernel before updating. Inspect the kernel and
loader package versions together, preserve and verify recovery artifacts, and
verify the updater output and initramfs before a boot trial. Stage one remains
unchanged and cannot automatically fall back if stage two fails.

Aura, U-Boot, the kernel, the four Mesa split packages, audio and UCM are held
in pacman's `IgnorePkg` pending reviewed updates. Aurora's current Mesa package
version compares newer than the local build, so without that hold a normal
upgrade would replace the tested graphics stack. `python packages/tools/aurora-update-report.py`
compares versions in the locally synced databases, including held packages; it
does not verify live upstream sources or signatures.

The earlier PR-stack snapshot and staging tools are historical; their source and
qualification notes are available in Git at commit `dc600bb`. They are not the
current build workflow.
