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

Git's current branch is traversable. A `git fsck` audit found empty objects
and invalid or incomplete Codex-owned historical checkpoint references. The
two empty capture refs and eleven empty loose object placeholders were saved in
`out/git-damaged-metadata-20261028.tar.gz` and removed. One historical Codex
checkpoint still refers to a missing Mesa tree and test blob; those contents
have not been recovered. The current branch and remote-tracking history are
traversable without missing objects.

An extracted upstream U-Boot review tree was removed after all 38,034 files
and symlinks matched the retained `out/boot-upstream-review/aurora-pr16-head.tar.gz`.
The extracted KWin 6.8.1 tree was also removed after all 3,251 files and links
matched its retained `out/kwin-vrr/kwin-v6.8.1.tar.gz`. The retired VRR force
kernel source was archived to `out/vrr-force/source-retired.tar.zst` and
compared to the extracted tree before removal; its checksum is alongside it.
Other local builds and captures remain pending dependency and provenance review.

Upstream review on 28 October: [Aurora distribution catalogs](https://github.com/aurora-silicon/aurora-distributions) document signed distribution delivery and private calibration handling, while [Asahi update-m1n1](https://github.com/AsahiLinux/asahi-scripts/blob/main/update-m1n1) assembles the boot bundle and keeps an old copy when it changes. Neither establishes a qualified replacement for this J614s package workflow.
