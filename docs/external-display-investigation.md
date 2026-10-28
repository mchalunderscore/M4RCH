# J614s external display investigation

> Historical trial services and ESP backups described below have been retired.
> Trial sources are preserved in `out/retired-experiment-sources-20261028.tar.gz`;
> see [boot recovery](installation-maintenance.md) for the current setup.

HDMI and USB-C produced a picture in the successful trial, including one USB-C-attached suspend/wake. The promoted normal entry booted on 28 October; external displays have not yet been tested with driver autoload. The sections below preserve the investigation chronologically.

## Upstream

- [Aurora Linux #446](https://github.com/aurora-silicon/linux/pull/446), merged as `6dc07e`, contains the desktop external-display infrastructure already present in the current kernel lineage.
- [Aurora Linux #451](https://github.com/aurora-silicon/linux/pull/451), inspected at `0d43a7f471acfa5b24893f43bb0d86d5021706b1`, supplies the J616s HDMI and USB-C routes, the PMP-aware power gate and subsequent fixes. Its discussion reports successful direct HDMI and USB-C tests on J616s. The power stages must be sequenced: upstream reports that enabling them together crashed a DCP.
- [Aurora Linux #515](https://github.com/aurora-silicon/linux/pull/515), inspected at `48fe30da9842007954558d215edae084c90ee1ff`, integrates the in-progress work. Its changes do not cleanly apply as a unit to this kernel, which already includes overlapping and local display changes.
- [Aurora m1n1 #56](https://github.com/aurora-silicon/m1n1/pull/56), inspected at `1bf9ec57556dab22886bfb31faa3edc1f345a607`, derives external DCP firmware memory from the current boot's ADT, validates the segments, and publishes disabled placeholders transactionally. It does not turn on the processors; the kernel's power gate does so only after the handoff and PMP are ready.
- [Aurora Linux #516](https://github.com/aurora-silicon/linux/pull/516) concerns an additional two-lane Type-C pin assignment. It is not evidence that this Mac requires that path; validate the negotiated mode before choosing it.

Upstream targets J616s. An address match alone does not establish that the complete power, pin, firmware and Type-C routing contracts are correct for J614s.

## Evidence from this Mac

The existing macOS IORegistry capture identifies the HDMI path via ATC3 and `dcpext0`. The Linux boot preserves the live ADT, so an additional macOS boot was unnecessary for the initial comparison. A read-only capture was audited by `experiments/external-display/audit-adt.py`: the external DCP, display, DART and crossbar register ranges and selected interrupts agree with the inspected upstream topology. Both external firmware descriptions have the expected four segment flags, report preloaded/running in the boot ADT, share panel TEXT, and have disjoint writable external segments. These checks do not prove current coprocessor state or validate the complete power and memory contract. The raw ADT is private under `out/external-investigation/private/`; it must not be published.

The installed J614s DT does not describe the external controllers. The machine uses m1n1 followed by a custom U-Boot bridge, which transfers selected live-tree handoff data to a separate Linux template. Aurora's m1n1 handoff alone therefore cannot reach Linux: the bridge must also transfer each external controller's firmware properties and remap every reserved-memory/IOMMU owner phandle into the Linux tree. Its existing implementation recognizes only the internal DCP, display and PIODMA owners. Care is needed around shared TEXT and failed or partial publication, while keeping the existing internal handoff intact.

The local kernel's J614s five-display-window check applies to all desktop DCPs, although the external nodes have a different mapping. `experiments/external-display/dcp-internal-only.patch` limits this internal-panel check to the internal processor, leaving the upstream external path in place. It has been checked for application, but not built or boot-tested.

The [m1n1 external-handoff patch](../packages/m1n1-m4rch/promoted-source/external-handoff.patch) ports Aurora's external handoff logic onto the reconstructed loader at `1efafe1fe0ec134b89d55c2cc64106a66a4df2b7`, after the existing J614s adaptations. At this point in the investigation the resulting loader had built but had not yet been booted. The upstream code requires the panel handoff marker and validates each external controller's current ADT and memory before publishing its regions.

## Remaining integration

1. Reconstruct and verify the exact installed U-Boot source/build and its Linux template; add disabled J614s controller/route nodes and memory placeholders to both appropriate trees.
2. Implement and test the external reserved-memory bridge with distinct source and destination phandles, shared TEXT, rejected or partial handoffs, and no regression in internal-display admission.
3. Adapt Aurora's external gate and device tree to the J614s, verifying all power domains, pin control and routes against its ADT. Integrate the upstream driver changes selectively, including the local internal-only fix. Build and test the resulting stack offline.
4. Prepare a recoverable attended boot trial preserving the working loader, kernel and initramfs. The keyboard does not work in GRUB, and a pre-GRUB loader failure cannot be recovered by choosing another menu entry; recovery may require external media/macOS to restore the saved boot bundle. Test HDMI, then USB-C, including hotplug and sleep, only after the trial is ready.

No working external display is claimed until the complete chain has booted and a physical display has been tested.

## External-display trial, 2026-10-27

The trial is armed for the next boot. Its separate kernel release is `7.3.0-m4rch-vrr-ext`, with `m4rch.extdisp=1` selecting the J614s external gate. The default GRUB entry temporarily points to `m4rch-external-trial`. The enabled `m4rch-external-restore.service` checks the saved and candidate hashes and restores `/boot/boot.bin` and `/boot/grub/grub.cfg` before graphics startup. The working originals are `/boot/boot-before-external-trial.bin` and `/boot/grub/grub-before-external-trial.cfg`. If the new loader fails before Linux runs the service, the owner cannot select a GRUB entry with the current keyboard setup; external media or macOS is needed to restore the saved `boot.bin` and, if necessary, the saved GRUB config. Do not overwrite the backups until the trial and rollback are verified.

The exact installed U-Boot binary was reconstructed byte-for-byte from the pinned Aurora source, retained J614s adaptations and the default-handoff patch. The candidate adds transactional external DCP memory remapping and boot-ADT ATC3 PHY tuning; it leaves power and devices disabled for the kernel gate. A refused loader handoff keeps its disabled placeholders without causing the existing bridge's duplicate-reservation error. The new m1n1 binary builds from reconstructed source with Aurora #56's external-memory code, but its reconstructed baseline binary is not byte-identical to the installed m1n1 (the Rust toolchain/build paths differ); this adds uncertainty to the pre-GRUB trial.

The candidate control and Linux-template DTs preserve all 1,778 and 1,814 pre-existing properties respectively. All 33 Aurora gate-stage nodes begin disabled. The live ADT shows FAB7's parent is AFI on J614s; the trial uses AFI instead of J616s' FAB6. The external CPU domains remain disabled. The selected PMP records and HDMI GPIO controls match the upstream topology. The first six ATC3 DP tuning tables match Aurora's J616s table; three other tuning tables differ, and the bridge reads all nine from the current boot's ADT rather than copying J616s tuning.

A three-way merge brought Aurora #451 into the isolated kernel, retaining the local J614s VRR policy and wake fix. Both the display module and the power/PHY components compile; the image, 250 modules and initramfs were built under the separate release. The trial initramfs contains the same 50 module paths as the working image, including the candidate PHY module. A host test runs the actual m1n1 publisher into the actual U-Boot bridge and checks both memory maps and disabled hardware; the existing internal handoff and m1n1 T8122 regression tests pass. The local VRR admission, wake, and reapply tests pass against the merged source; Aurora's 14 PHY host cases pass. Its lifecycle suite passes the new resource and six actual disconnect/recovery fixture cases after fixture updates. Six other lifecycle cases fail to compile in both the trial and unmodified baseline harness, so they are not counted as passes.

The physical trial has not yet booted and no external display is claimed working. On return, verify the running release, command line, automatic boot-file restoration, and kernel display/power logs before testing HDMI, then USB-C. The offline manifest and candidate artifacts are under `out/external-investigation/trial/`.

### First physical boot and corrected retry

The first trial booted `7.3.0-m4rch-vrr-ext`, and the rollback service successfully restored the working `boot.bin` and GRUB configuration. Both firmware handoffs arrived in Linux, and the PMP gate enabled HDMI stage 0 and USB-C stage 1. Neither external DCP bound: the journal explicitly reports `t6041_dcpext=0`. The system's existing `/usr/lib/modprobe.d/apple-silicon.conf` sets that option to zero, overriding the upstream driver's enabled default. The first trial therefore did not exercise HDMI link training or sink detection. The internal panel and VRR mode did start; the user reported no HDMI output.

The corrected retry is armed with `appledrm.t6041_dcpext=1` on its trial-only kernel command line. A `modprobe --show-depends appledrm t6041_dcpext=1` check shows the explicit value after the existing zero option; the baseline configuration remains unchanged. The candidate and backup boot and GRUB hashes were rechecked, and the same enabled service will restore both working files once the trial reaches userspace. Before userspace, a loader failure still requires the saved bundle to be restored externally.

### HDMI result

The corrected trial booted with `appledrm.t6041_dcpext=1`; the restore service returned the normal loader and GRUB files, verified by matching their saved SHA-256 hashes. Both external DCPs initialized and Linux reported `HDMI-A-1` connected. The user confirmed a picture and considers HDMI working. They observed shadow flicker and unusual scaling and suspect their KDE/Karousel setup; that attribution has not been independently verified. HDMI is marked working for basic output on the trial, while hotplug, suspend, USB-C, and a permanent promotion remain unverified.

### USB-C result

During the corrected trial, the HDMI monitor was disconnected and a TV was connected over USB-C. Linux reported `DP-3` connected and listed modes including 1920×1080. The external DCP acquired the Type-C route and the user confirmed a visible desktop on the TV. No external-controller or DART fault was found in the filtered kernel log after the change. Both HDMI and USB-C have therefore passed basic picture tests on this trial; the bootloader and GRUB default had already been restored to the working baseline. Reconnection, sleep/wake with a display attached, multiple ports and simultaneous displays have not been qualified.

### Sleep and promotion

With the USB-C TV attached, the user authorized a system suspend and reported that both the laptop display and TV returned normally. The journal confirms s2idle entry and exit, the USB-C crossbar restoring its route after power loss, and the external DCP reconnecting. A later connector disconnect was confirmed by the user to be their intentional unplug.

The tested stack has been promoted: `linux-m4rch 7.3.0-9`, `m1n1-m4rch 20261025-2`, and `u-boot-m4rch 2026.07-3`. The normal `Arch Linux` GRUB entry includes `m4rch.extdisp=1 appledrm.t6041_dcpext=1`, as does its persistent GRUB drop-in. The promoted `/boot/boot.bin`, kernel and initramfs were verified byte-for-byte against the successful trial artifacts. The normal entry itself has not been booted separately since promotion. The current session is still running the successful trial kernel.

The preceding loader, kernel, initramfs and GRUB configuration are saved on `/boot` under `before-external-promotion` names; the preceding `7.3.0-m4rch-vrr` module tree was archived under `out/external-investigation/promotion/backup/` and restored alongside the new tree. If a pre-GRUB failure prevents booting, recover by restoring the saved boot bundle and GRUB configuration from external media or macOS; the keyboard is unavailable in GRUB. The package sources include the Linux and loader patches, and the combined U-Boot patch was applied to the pinned upstream source and compared with the actual tested handoff and embedded template.

Basic HDMI and USB-C output, HDMI-to-USB-C switching, and one USB-C-attached suspend/resume are verified. The reported HDMI shadow flicker and scaling remain uninvestigated, and simultaneous displays and other ports have not been qualified.
