# Current system status

This is a snapshot of the J614s machine on 31 October 2026, not a general
support matrix. Check the installed versions and running kernel before an
update. The owner confirmed the retained-input trial booted and worked
normally; the newly installed default has not yet booted. Peripheral and
workload checks below are limited to the stated runs.

| Component | Installed package or running release |
| --- | --- |
| Linux | `linux-m4rch 7.3.0-26`; running `7.3.0-m4rch-mtp-trial` |
| m1n1 | `m1n1-m4rch 20261031-1` |
| U-Boot | `u-boot-m4rch 2026.07-19` |
| Native Mesa | `mesa-m4rch 1:26.3.0.r20261031.c208afc-1` |
| Platform configuration | `asahi-scripts-m4rch 20261026-3` |
| Audio profiles | `alsa-ucm-conf-m4rch 1.2.16.1-4` |
| Fans | `mbpfan-m4rch 2.4.0-4` |
| Power profiles | `power-profiles-daemon-m4rch 0.30.r20261028.1a151cc-1` |
| Steam launcher | `steam-m4rch 1.0.0.81-12` |

`/boot/boot.bin` contains m1n1, the J614s device tree and U-Boot. The owner
confirmed GRUB keyboard input and Linux keyboard and trackpad on the retained
MTP trial. The rebuilt final `7.3.0-m4rch` kernel and U-Boot are installed in
package-managed paths. The owner chose promotion without a verification reboot,
so the final default has not yet been booted. GRUB has
one entry selecting `/boot/vmlinuz-linux-m4rch` and
`/boot/initramfs-linux-m4rch.img`. See the [recovery guide](recovery.md) and
package source records for provenance.

Native Mesa `c208afc` enumerated the actual M4 Pro GPU and completed a short
Vulkan rendering run; OpenGL reported Zink on that GPU. Steam and longer
rendering workloads were not qualified on this exact Mesa update. The owner's
positive Steam and Shinri observations were made on an earlier stack. The Steam client and supporting libraries live in the user's Steam
directory, so the launcher package alone does not produce a fresh install.

The `user4k=on` kernel argument remains enabled for Steam. The normal command
line also enables the T6041 external-display path and blacklists the internal
speaker amplifiers. The owner reported camera and microphone operation on an
earlier build. A previous HDMI and USB-C display trial showed a picture, with
HDMI flicker and scaling issues; external displays and microphone capture were
not separately qualified in the latest rebase. See
[speaker safety](j614s-speaker-safety-investigation.md) before changing the
speaker policy.

Earlier lid suspend/wake trials passed on AC and battery; hibernation and
hybrid sleep were disabled. This machine has a local sleep override enabling
suspend while the installed platform package retains an older default. The
recent boot confirmation is not a fresh suspend test. An unsuccessful wake
may require a power-button reset; no automatic wake timer has been verified.

Earlier local experiments requested forced panel VRR and custom HDR behavior.
The upstream display-gate integration removed those local changes; their
reported results do not establish VRR or HDR behavior on the current kernel.

The last boot log still reported a PMP `power-controller@490` parent-domain
failure and its deferred child. The previously investigated PMP startup
proposal is not part of the installed kernel; a successful desktop boot does
not establish that the warning or deferred devices are resolved.

The `mbpfan-m4rch` service controls both fans through macsmc. Its local
curve filters CPU Die Max over eight seconds and ramps from 75 to 90°C; an
invalid reading or a raw temperature of at least 90°C requests full speed.
Sustained load and wake have not been qualified on the current kernel.

The installed power-profiles daemon uses experimental J614s CPU frequency caps
in power-saver; balanced and performance restore the available ceilings.
The service attempts to preserve external limits, but CPU sysfs has no atomic
compare-and-swap and an abrupt daemon termination can leave a cap in place.
Avoid running competing frequency managers. Earlier power-saver and wake
trials predate the current boot stack.
