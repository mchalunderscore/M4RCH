# AURT002 — Aurora J614s test

This candidate is untested on native hardware. Boot M4RCH normally after
staging; GRUB selects `Aurora J614s test 2 (speakers disabled)`.
AURA001 and older payloads are preserved; their original loader/GRUB pair can
be restored from macOS.

Includes Aurora integration `1aa2857509d5` and pending M4 Pro series
#406, #408, #409, #410, #411 and #412. Mesa is Aurora `76155824118a`
with T6040 PR #55. #413 was omitted because its queue implementation
conflicts with the selected GPU series.

The test U-Boot handoff adapts the board from this boot's FDT/ADT: memory, fused CPUs,
release addresses, radio calibration, per-port USB tuning, PMP information,
GPU reservations and two-cluster GPU/CS/AFR OPPs. GPU startup requires
`mBoot-18000.161.10` (25G83). Unknown/incomplete GPU data leaves the GPU and
its power provider disabled. Boot receipts appear under `/proc/device-tree/chosen/`.

Speakers are excluded both from the device tree and compiled modules.
USB/Bluetooth audio remain available. The AOP/internal microphones, headphone
jack, camera and DCP/external display takeover remain disabled in this first
profile: this test loader does not yet implement their qualified DMA/firmware handoffs.
The existing framebuffer desktop stays in place; this test does not replace
the system's Mesa packages or claim accelerated Plasma composition.

Inside Linux:

```sh
uname -r                     # 7.3.0-m4rch-aurora-test2+
cat /run/aurora-test/startup.log
ls -l /dev/dri
/run/aurora-test/with-mesa vulkaninfo --summary  # if vulkan-tools is installed
/run/aurora-test/with-mesa glxinfo -B           # if mesa-utils is installed
sudo sh /run/aurora-test/collect.sh
```

The wrapper selects the private Mesa prefix only for that command.
Modules and Mesa are bound from `/run` for this boot; installed packages and
the existing modules are not replaced. One empty `/opt/m4rch-aurora-test2`
mount-point directory may remain on the root filesystem after reboot.

If boot fails, power down after storage activity has stopped, return to macOS,
mount the ESP, and restore the saved loader and GRUB configuration:

```sh
sudo diskutil mount disk0s3
python3 /Users/michal/Projects/Personal/arch-m4/experiments/aurora-test/select_boot.py previous
```

For an Aurora boot without GPU startup, use `framebuffer` instead of `previous`.
Use `test` to select the normal AURT002 candidate again. The selector checks
the mounted ESP identity and makes another configuration backup.
Staging replaces `boot.bin`; rollback restores its verified previous copy together
with the previous GRUB config. Apple enrollment and stage 1 stay unchanged.
The old menu entries require that previous loader; restore the pair before using them.
Do not replay the historical GPU launchers from other ESP directories.
