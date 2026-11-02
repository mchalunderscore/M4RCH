# J614s hardware status

This is a concise summary of observations on the combined J614s Aurora stack, not qualification of an unmodified upstream installation. The forked kernel booted with Aurora's default initramfs configuration, and the normal packaged kernel subsequently booted. Check the current GRUB menu separately. See the linked reports for exact software, tests and limitations.

| Area | Evidence and remaining work |
| --- | --- |
| Boot, display, input, storage | The forked kernel booted with Aurora defaults and working internal display, keyboard, trackpad, Wi-Fi and NVMe root. See [status](docs/status.md) and [recovery](docs/recovery.md). |
| GPU | The desktop and short render and compute tests worked with the submitted 16-core admission. GPU preemption and the assumed buffer layout remain unqualified. See [hardware limitations](docs/hardware-limitations.md). |
| Touch ID | Enrollment and authentication worked on the combined stack, including after a reboot. The enrolled identity was restored during the default-only trial; authentication was not independently tested in that boot. See [hardware limitations](docs/hardware-limitations.md). |
| Microphone and camera | The owner confirmed clear microphone recording and a live camera image in combined trials; channel characterization, tuned camera quality and resume remain unqualified. See [upstream work](experiments/j614s-upstream/README.md). |
| Speakers | Disabled pending J614s-specific protection and qualification. See [hardware limitations](docs/hardware-limitations.md). |
| SD reader | A combined trial detected an SDXC card and the owner mounted and edited files. Suspend and long-term I/O remain unqualified. |
| USB and displays | USB 3 read checks passed on all three ports in both orientations in a combined trial. HDMI worked on an older loader; HDMI with the newer handoff and USB-C display remain untested. |
| Headphone jack | The replacement PR-stack kernel has not been tested with wired headphones. |
| Thermal | The GPU allocator behavior was investigated on hardware; candidate trips and full thermal limits require further review. See [hardware limitations](docs/hardware-limitations.md). |
