# AURD001: direct Aurora J614s hardware test

Boot the existing M4RCH entry. GRUB selects
`Aurora direct J614s (built-in speakers disabled)`.
Expected kernel: `7.3.0-m4rch-aurora-direct1+`.

Revision 1 reached initramfs on this machine but failed with ANS RTKit
endpoint discovery timeout (-62), then NVMe root not found. The keyboard
was unavailable before runtime driver loading; CPU count was not captured.
Revision 2 retains the live ANS session and its DMA allocation arena, loads
input drivers before storage, and prints the actual online CPU range.
Revision 2 stopped in U-Boot before GRUB: its arena check omitted U-Boot's
124 KiB environment allocation. Revision 3 uses TOTAL_MALLOC_LEN, matching
mem_malloc_init, and prints individual handoff failures plus CPU/arena details.
Revision 3 then exposed a second guard bug: it assumed the running CPU had
MPIDR zero. m1n1 intentionally leaves the actual boot CPU's release address
zero. Revision 4 reads U-Boot's running MPIDR, permits zero only for that CPU,
and records the correct boot CPU in the output FDT header. Every secondary
still requires a nonzero live release address. CPU online count remains
unverified until Linux starts. Revision 4 reached Arch userspace and mounted
the NVMe root. Keyboard/trackpad and Bluetooth initialized; Wi-Fi firmware
failed to start, CPU frequency setup referenced fused CPU nodes, and the GPU
module-loading check skipped the /proc/device-tree symlink.

Revision 5 removes fused CPUs and their topology references, preserves the
live Wi-Fi antenna SKU used for firmware selection, and explicitly loads
the admitted GPU driver. It increases the log buffer to retain early SMP
messages. Its hardware changes still require a native test. Kernel drivers are
Aurora integration `420a1c8f5492`, with no pending PR stack. Mesa is Aurora
`4911479bf988`. Local changes are the J614s board template, live boot handoff,
temporary userspace setup and speaker exclusions.

The normal candidate attempts GPU rendering, keyboard/trackpad, Wi-Fi,
Bluetooth, USB3/reconnect, NVMe, CPU frequency/thermal management, microphones,
headphone/headset jack, ambient light/lid angle sensors, camera, keyboard
backlight and suspend-to-idle. Driver availability is not hardware qualification.
GPU/AOP/ISP startup requires supported 25G83 firmware and complete live handoff
information. Missing data leaves that device disabled. Camera sensor discovery
and userspace capture still need a native test.

Built-in speaker cards and amplifiers are disabled in the device tree, and
TAS2764/TAS2770 modules are omitted from the package. Headphone, USB and
Bluetooth audio are allowed. No audio/video is recorded automatically.

The internal display keeps its working framebuffer. Current Aurora does not
provide a qualified J614s DCP firmware profile: native display takeover,
brightness and external display support remain unavailable. GPU power-model
coefficients remain Aurora's constants; they are not newly measured J614s
calibration. The loader supplies this machine's GPU operating points and
reservations and sets the complete conditional GPU power dependency graph.

The existing desktop session stays available. At the login screen,
`Plasma (Aurora GPU test)` launches Plasma with the private Mesa stack.
This is an optional acceleration experiment; GPU rendering and the complete
desktop/compositor path need separate native checks.

Inside Linux:

```sh
uname -r
cat /run/aurora-direct/startup.log
cat /proc/asound/cards
ls -l /dev/dri /dev/video* /sys/bus/iio/devices/
/run/aurora-direct/with-mesa vulkaninfo --summary  # if installed
/run/aurora-direct/with-mesa glxinfo -B           # if installed
sudo sh /run/aurora-direct/collect.sh
```

Suspend-to-idle and lid suspend are enabled temporarily in the normal test;
hibernation stays disabled. Capture, headphone playback, USB transfers and
suspend/resume require owner testing.

Modules, Mesa, ALSA UCM, session definitions and sleep overrides live in RAM
for this boot. Installed packages and user files are preserved. Empty mount
point directories may remain after reboot. Apple enrollment/stage 1 stay
unchanged. `boot.bin` and GRUB are installed as a matched pair.

For recovery, return to macOS:

```sh
sudo diskutil mount disk0s3
python3 /Users/michal/Projects/Personal/arch-m4/experiments/aurora-direct/select_boot.py stable
```

`stable` restores the original native-validated loader/configuration.
`previous` restores the pair recorded at staging; from revision 2 onward this
is the original stable pair. It does not select the archived native revision.
`framebuffer` selects AURD001 with the original m1n1 component, GPU off,
AOP/camera off, and the old sleep policy retained. `test` selects the full
candidate again. Each choice checks saved checksums and restores both loader
and GRUB. Older GRUB entries need their matching old loader restored first.
