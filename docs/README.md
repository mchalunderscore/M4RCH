# Documentation

Start with the [project README](../README.md) for current working features and
[package guide](../packages/README.md) for installed versions and build limits.
The investigation notes preserve dated tests in chronological order; an early
trial result does not necessarily describe the final promoted setup.

## Current investigations

| Topic | Guide |
| --- | --- |
| Suspend and wake | [Suspend and boot](suspend-boot-investigation.md) |
| Driver startup | [Autoload trial](driver-autoload-investigation.md) |
| Internal display and VRR | [VRR](vrr-investigation.md), [HDR](hdr-investigation.md), [KWin submission](kwin-submit-investigation.md) |
| HDMI and USB-C displays | [External displays](external-display-investigation.md) |
| Power profiles | [Power profiles](power-profiles-investigation.md) |
| Speaker protection | [J614s speaker safety](j614s-speaker-safety-investigation.md) |
| Bootloader comparison | [Aurora U-Boot comparison](boot-upstream-comparison.md) |
| Steam and graphics | [Steam acceleration](steam-acceleration.md), [GPU and memory](gpu-reclaim-investigation.md), [Plasma memory](plasma-memory-investigation.md) |
| Fans and temperatures | [Fan investigation](mbpfan-investigation.md), [Plasma CPU temperature](plasma-cpu-temperature.md) |
| Upstream review | [Opportunities reviewed on 27 October](upstream-opportunities-2026-10-27.md) |
| Uncommitted work | [Worktree review](worktree-review.md) |
| Repository cleanup | [Installation and maintenance cleanup plan](repository-slimming-plan.md) |
| Installation and recovery | [Maintenance inventory](installation-maintenance.md) |

## Historical records

The earlier SD-card workflow and dependent Aurora trials were retired from the
working tree. Their tracked sources remain in Git history at `bce491f`. The
following guides preserve historical evidence, not current operating procedures:

- [Hardware](hardware.md), [architecture](architecture.md) and
  [development](development.md).
- [Bootloader alignment](bootloader-alignment.md), [split internal boot](split-boot.md),
  [setup](setup.md), [stub upgrade](stub-upgrade.md) and [NVMe root migration](nvme-root.md).
- [CPU experiments](cpu-performance.md), [left USB trial](left-usb-trial.md),
  [USB provenance](usb-patchset-provenance.md) and [GPU register mappings](gpu-register-map.md).
- The historical [handover](../HANDOVER.md). The retired native-agent guides
  remain available in Git at `3e5fb15`.

Dated evidence receipts remain under [evidence/](evidence/). The historical
GPU trial receipts from 8–11 October have been retired from the working tree; the
[archive index](evidence-archive.tsv) lists their original paths and Git blob
IDs at commit `bce491f8716aef6b23e60e1d5909e5be8d7f88f9`. To inspect one, run
`git show bce491f:<path>`; to restore one to the working tree, run
`git restore --source=bce491f -- <path>`. Historical trial conclusions and
logs can be retrieved from the archive; remaining receipts cover other dates
and work.

Ignored `out/` directories include local builds and machine-specific captures;
Git history cannot restore ignored or untracked files.

Retired trial and diagnostic sources, including unique uncommitted material,
are preserved locally in `out/retired-experiment-sources-20261028.tar.gz` and
`out/retired-diagnostics-20261028.tar.gz`. They are not in Git; back them up
separately if they need to be retained. Historical commands in the notes may
refer to retired files, kernels and boot entries and should not be run as
current procedures.

The fuller versions of several condensed notes are in
`out/documentation-before-condensing-20261028.tar.gz`. The local
`out/worktree-snapshot-20261028.tar.gz` contains the tracked and untracked
working files before the local commits, plus the prior Git diff and status; it
does not contain ignored build inputs, firmware or private captures.
