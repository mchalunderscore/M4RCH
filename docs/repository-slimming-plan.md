# Remaining installation and maintenance cleanup

The SD-image workflows, obsolete trials and their test-only machinery have
been substantially retired. Their tracked predecessors are in Git history at
`bce491f`; unique uncommitted trial material and the previous cleanup plan are
preserved in the local archives listed in the [documentation index](README.md).

Remaining work:

1. Qualify a package build and update path for the installed kernel, bootloader
   and power-profile daemon. Preserve ignored promotion inputs until replacements
   are verified; review the machine-specific U-Boot UUID before reuse.
2. Trace remaining disk, firmware, enrollment and image-building libraries and
   separate useful recovery functions before retiring obsolete callers, patches
   or tests.
3. Audit `out/` by dependency and provenance before removing old builds or
   captures. It includes private device data and inputs used by preparation.
4. Continue condensing historical evidence when its useful conclusions,
   provenance and unique uncommitted contents are preserved.

See the [maintenance inventory](installation-maintenance.md) for the current
boot, tested behavior and build limitations. See [worktree review](worktree-review.md)
for publication and backup considerations.
