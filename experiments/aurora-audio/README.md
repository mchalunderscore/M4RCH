# J614 microphone and combined Aurora candidate

AUMI001 r13 is installed as the default `m4rch-aurora-dcp001` entry on the
M4RCHESP. It reuses the native-booted r12 kernel `7.3.0-m4rch-aurora012`.
The microphone still needs native validation.
The user performs all reboots. Built-in speakers remain disabled.

The fresh r12 return is saved under `out/aurora-audio/native-r12`. It shows
AOP disabled with handoff error -15, DAPF readiness 3, and no ALSA cards.
The offline SRAM fix in r12 did not resolve that native rejection.

r13 enables AOP in the m1n1 control tree so the existing Aurora upstream
AOP firmware publisher runs (m1n1 #41, already in the unchanged pinned binary).
U-Boot now transfers that same-boot code/log reservation data, rebases consumer
phandles and enables the AOP DART. Unused calibration RAM stays reserved without
an obsolete IOMMU consumer reference. The kernel, modules, Mesa, UCM and final
speaker-free Linux template are byte-identical to r12. The module option was
verified from the actual initramfs; an older extracted init copy was stale.

Rebuild preparation: `prepare_standard_aop.py /path/to/pinned-r12-uboot`,
then build U-Boot and run `package_standard_aop.py` and
`stage_standard_aop.py --apply`. The saved full loader patch, validation and
installation receipts are under `out/aurora-audio/r13`. Host handoff checks
cover both SRAM/DRAM calibration layouts, consumer phandle rebasing, malformed
mapping refusal and DAPF refusal. The collector now saves same-boot AOP segment
metadata and capture configuration/PipeWire state without recording audio.

The r13 per-candidate rollback restores r12's loader/default (with the retired
r9 entry removed):

    python3 /Volumes/M4RCHESP/AUDP001/r13/revert.py

The r12/r10 GRUB fallbacks and original pre-DCP rollback are retained. The
obsolete r9 initramfs is archived, hash-verified, under r13's host output before
removal from the ESP. Earlier revision-specific rollback scripts were written
for their then-current GRUB hashes; use r13's rollback for the current candidate.

The following describes the unchanged r12 kernel and audio runtime baseline.

The kernel starts at Aurora Linux `ff1510ce2d2c25077948a78beba8cc32fb7068c1`
and carries reviewed PRs #436, #437 (including its #434 dependency), #451 and
#453. Existing #429/#433 fixes and the native-tested J614 six-resource display
adaptation and 16-core GPU opt-in remain. #427/#428/#435/#448/#452 are in the
new baseline. Exact rebuild changes are in `out/aurora-audio/r12/kernel-combined.patch`
and `uboot-j614s.patch`, alongside the config, module symbols, pins and hashes.

The microphone graph comes from asahi-audio #11, commit
`68b496e2f668c210c3e3a3ac1dd5de3ef9142023`, adapted to J614 card/node names.
The HPAI UCM entry follows alsa-ucm-conf-asahi #7. Its shared three-channel
profile is already in the original runtime. The capture configurations are
RAM overlays, with the existing userspace settings preserved. The graph is a
three-channel average, gain and high-pass filter, not microphone beamforming.

AOP firmware reservations now contain external code and the identity-mapped
OS log, matching the kernel's nCal=0 boot flow. Requiring __EDATA in DRAM
incorrectly rejected the SRAM layout. The new AOP node exposes only `dma`,
`cout`, `cin`; speaker/sense streams, speaker cards and amp drivers are absent.
The loader also provides same-boot GPU firmware TEXT for upstream loaded-image
identification. No firmware hash checks are bypassed.

The internal panel retains the r10 display handoff and Mesa runtime. External
routing/USB3 lane-reclaim code is included, but external DCP processors remain
disabled until the J614 loader/DT handoff is implemented. Display suspend and
VRR retain their previous disabled policy.

Validation: kernel, modules and DTBs built; 248 matching modules packaged;
63/63 upstream display/USB host checks passed; full loader tests passed with
both DRAM and SRAM AOP-data fixture layouts; PipeWire constructed the expected
`effect_output.j614-mic` source in an isolated VM. These are offline checks,
not native microphone or GPU qualification. Build and validation receipts are
under `out/aurora-audio/r12/`.

The native-tested r10 kernel/initrd remain in GRUB. To restore its full
loader and default entry from macOS with the ESP mounted:

    # Historical r12 installation: use r13/revert.py for the current candidate.

The original pre-DCP `AUDP001/restore.py` rollback remains valid too. Only the
obsolete r8 initramfs was retired, after hash-verified archival under r12's
host output. Current ESP hashes and retained payloads were read back and
verified after promotion. No enrolled stage1 change and no reboot occurred.

After boot, test the built-in microphone in the desktop input settings and
confirm GPU acceleration/120 Hz. Save a fresh return bundle with:

    sudo sh /run/aurora-direct/collect.sh

The collector includes microphone card and PipeWire source information; it
does not record audio.
