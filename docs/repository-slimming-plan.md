# Remaining installation and maintenance cleanup

The SD-image workflows, obsolete trials and their test-only machinery have
been substantially retired. Their tracked predecessors are in Git history at
`bce491f`; unique uncommitted trial material and the previous cleanup plan are
preserved in the local archives listed in the [documentation index](README.md).

Remaining work:

1. Qualify a package build and update path for the installed kernel, bootloader
   and power-profile daemon. The bulk lists and checks were aligned on 28 October,
   but an end-to-end disposable build has not run. Preserve ignored promotion inputs until replacements
   are verified; review the machine-specific U-Boot UUID before reuse.
2. Trace remaining disk, firmware and enrollment libraries and separate useful
   recovery functions before retiring obsolete callers, patches or tests. The
   orphaned kernel/loader image builder and its dedicated tests were retired;
   their earlier versions are available in Git at `3e5fb15`.
3. Audit `out/` by dependency and provenance before removing old builds or
   captures. Regenerable compiler intermediates from four retired trial source
   trees were removed on 28 October, freeing about 1.9 GiB; source trees,
   promoted inputs, firmware and private captures remain.
4. Continue condensing historical evidence when its useful conclusions,
   provenance and unique uncommitted contents are preserved.

See the [maintenance inventory](installation-maintenance.md) for the current
boot, tested behavior and build limitations. See [worktree review](worktree-review.md)
for publication and backup considerations.

Git's current branch is traversable, but `git fsck` still reports empty objects
and invalid or incomplete Codex-owned historical checkpoint references. They
are not needed to build the current branch; reconstruct the missing checkpoint
data or preserve it before changing those app-owned references.

Upstream review on 28 October: [Aurora distribution catalogs](https://github.com/aurora-silicon/aurora-distributions) document signed distribution delivery and private calibration handling, while [Asahi update-m1n1](https://github.com/AsahiLinux/asahi-scripts/blob/main/update-m1n1) assembles the boot bundle and keeps an old copy when it changes. Neither establishes a qualified replacement for this J614s package workflow.
