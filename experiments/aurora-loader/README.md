# AURL001: Aurora m1n1 and U-Boot on J614s

This changes the ESP-loaded second-stage loader to Aurora m1n1 aurora-wip
`9f7cdfbd0623d96f21965434c3a7dda799ffcff4` and Aurora U-Boot aurora-wip
`7680260272f3612a13f0c9a6c7bfbc5e9ba7ce8c`. The enrolled first stage stays
unchanged. This candidate requires a native boot; a successful build is not
hardware qualification.

The existing accelerated AURG016 revision 4 kernel, initramfs, Mesa and default
GRUB selection remain unchanged. Built-in speaker playback remains disabled.
The normal boot therefore attempts the same Plasma/SDDM Wayland session.

Local adaptations retained:

- J614s board 4 MCC admission, keeping Aurora's register geometry, cache-state
  and firmware carveout checks. Its four controller windows, channel count and
  plane geometry match the owner's saved public IODeviceTree data.
- The native-tested MTP/AOP/ISP DAPF scope and checked SD-reader power action.
- Explicit ANS initialization using Aurora m1n1's existing implementation.
  Its RTKit session stays live; the allocator high-water interval is reserved
  and the usable RAM map refreshed after initialization.
- A T6041 NVMe subtype in Aurora U-Boot, following Aurora Linux's M4 Pro split
  BAR and LSQ-in-NVMMU layout. Aurora owns adoption, queues, mailbox responses,
  timeout handling and the final live session handoff. EFI disks stay read-only.
- The bounded J614s bootloader MMIO map, fixed ESP/EFI bridge and existing
  data-only Linux DT translation. The latter is still needed: switching forks
  alone does not supply Aurora with the complete J614s runtime board handoff.

The legacy bootloader control DT is retained with just the NVMe compatible
changed to `apple,t6041-nvme-ans2`. Its reg tuples and phandles stay intact.
Linux still receives the separate Aurora-derived J614s template and live data.
No Gravity source tree is used as either new bootloader's base. Some local
adaptations were carried forward from our Gravity-based setup.

Build in the existing `m4rch-aurora-build` VM with `/project` bound to this repo:

```sh
git clone --depth=1 --branch aurora-wip https://github.com/aurora-silicon/m1n1.git /work/aurora-native-loader/m1n1
git clone --depth=1 --branch aurora-wip https://github.com/aurora-silicon/u-boot.git /work/aurora-native-loader/uboot
git -C /work/aurora-native-loader/m1n1 submodule update --init --depth=1
python3 /project/experiments/aurora-loader/prepare.py /work/aurora-native-loader /project/out/aurora-loader
sh /project/experiments/aurora-loader/build.sh
```

Use new empty source directories. Preparation refuses a different revision or
dirty checkout. The build requires the ARM VM's existing GCC/Rust source,
Cargo cache, libfdt tools, image conversion tools and ordinary U-Boot packages.
Artifacts, exact source patches, result hashes and build logs go under
`out/aurora-loader`. Only public upstream code and local integration enter the
exported patches; no private Apple binary code is used.

On macOS, installation validates the physical ESP and active GPU kit, preserves
the previous loader on the ESP and host, then atomically replaces `boot.bin`:

```sh
python3 experiments/aurora-loader/stage.py install
python3 experiments/aurora-loader/stage.py verify
```

Native test: boot the existing Arch target normally. The U-Boot banner contains
`2026.07-AURL001`; m1n1 prints its `AURL001` handoff marker. Reach the existing
desktop and exercise normal input, Wi-Fi, storage, camera, USB and suspend.
Existing AURG016 collection records dmesg/journal and the live DT, including
`/chosen/m4rch,bootloader = AURL001`. If boot stops before Linux, photograph the
screen and return to macOS. No automatic reboot or timeout gate is introduced.

Restore the prior native-working loader after mounting the ESP in macOS:

```sh
python3 experiments/aurora-loader/stage.py restore
```

Or recover directly in Terminal (ESP must already be mounted):

```sh
cp /Volumes/M4RCHESP/AURL001/boot.previous.bin /Volumes/M4RCHESP/boot.bin
sync
```

The GRUB recovery entries are preserved, but cannot undo a loader failure that
occurs before GRUB. Restoring `boot.bin` from macOS handles that case. Existing
`aurora-direct/select_boot.py` choices also recognize AURL001 and restore their
own previous loader/configuration pair when selected.
