# Current system status

This is a snapshot of the J614s machine on 31 October 2026, not a general
support matrix. Check the installed versions and running kernel before an
update. The package-managed SD and jack promotion booted on 31 October (boot ID
`c7c08627-2c0d-4806-bf4b-3933df129d1b`). Peripheral and workload checks below are limited to the
stated runs.

| Component | Installed package or running release |
| --- | --- |
| Linux | `linux-m4rch 7.3.0-28`; running `7.3.0-m4rch-touchid` |
| m1n1 | `m1n1-m4rch 20261031-1` |
| U-Boot | `u-boot-m4rch 2026.07-21`; package-managed default booted |
| Native Mesa | `mesa-m4rch 1:26.3.0.r20261031.c208afc-1` |
| Platform configuration | `asahi-scripts-m4rch 20261026-3` |
| Audio profiles | `alsa-ucm-conf-m4rch 1.2.16.1-4` |
| Video decode | `libva-v4l2-request-m4rch 1.3.r11-2`; package-managed session default, H.264 and VP9 tested |
| Fans | `mbpfan-m4rch 2.4.0-4` |
| Power profiles | `power-profiles-daemon-m4rch 0.30.r20261028.1a151cc-1` |
| Steam launcher | `steam-m4rch 1.0.0.81-12` |

`/boot/boot.bin` contains m1n1, the J614s device tree and the newly packaged
SD U-Boot. The SD root port and card enumerated without the prior PIN1 conflict,
and the packaged jack card registered. The prior default booted with SEP active
and fingerprint login and sudo working; the SD and jack trials worked as
recorded in [FEATURES](../FEATURES.md).
GRUB has one persistent entry selecting the package-managed kernel and
initramfs. See the [recovery guide](recovery.md) and
[SEP/DCP investigation](j614s-sep-dcp-reservations.md).

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
