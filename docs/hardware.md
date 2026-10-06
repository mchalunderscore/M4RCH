# Hardware status

Target: **14-inch M4 Pro MacBook Pro, Mac16,8 / J614s / T6040**.
Native evidence currently covers a 12-core, 24 GB machine. This is an
experimental configuration, not certification of every device or workload.

| Device or function | Established behavior | Remaining work |
| --- | --- | --- |
| SD boot/root | Full m1n1 → U-Boot → SD GRUB → Linux boot; persistent ext4 and first-boot expansion; owner reports repeated boots/shutdowns without recurrence of the earlier ext4 incident | Original cause remains undetermined; investigate if new failures appear |
| Internal display | Software-rendered KDE, Firefox; native Wayland with active QPainter compositing verified | No GPU acceleration |
| Keyboard, trackpad, lighting | Native input and keyboard lighting have worked | Broader gestures/haptics and regression coverage |
| Wi-Fi | Connection, routing and traffic | Roaming and long-duration reliability |
| Bluetooth | Mouse input and AirPods Max A2DP playback | Headset microphone/duplex audio and broader devices |
| Right USB-C | USB2 YubiKey 5C at 12 Mbit/s and SanDisk storage at 480 Mbit/s in both orientations; reconnects and checked 16 MiB file write; earlier user-tested authentication | Hubs and sustained transfers; cached file read is not throughput evidence |
| Left USB-C | Both sockets enumerate YubiKey; owner confirms storage in both orientations; left-rear hub and USB microphone work | Sustained transfers, left storage write integrity, startup latency |
| USB3, Thunderbolt | No established device data path | PHY/host/altmode support |
| Internal NVMe | Namespace/partition discovery and reads through the ANS-aware loader | Writes, sustained I/O, failure recovery and shutdown qualification |
| CPU | Twelve cores; P/E capacity accepted; maintained SME/SME2 and all-core saved WFI passed native tests; owner reports actual 4.512GHz and WFI power savings | Sustained frequency residency, calibrated energy model and cooling qualification |
| Fans/temperatures | Fresh raw/hwmon readings; round six shows same-session mode3/zero RPM to mode0/changing RPM | Transition trigger, sensor meaning and fan ramp; continuous trace pending |
| Power | Battery/AC reporting and storage teardown | Battery energy decoding, physical shutdown/reboot qualification, suspend |
| Internal microphones / camera | Read-only macOS baseline captured: ISP/DART, CS42L84 codec and AOP/low-power mic endpoints; Linux paths unverified | Identify the internal array route and bring up capture without enabling speakers |
| Internal speakers | Playback remains disabled | Machine-specific protection model and fail-closed interlocks before playback |
| Brightness / external displays | No established functioning path | T6040/laptop support |

The [round-four receipt](evidence/2026-10-05-native-round4.json) establishes
native package migration to `7.1.3-m4rch` and `linux-m4rch`, `config-m4rch`,
`grub-m4rch`, `paru-m4rch`, using `update-a622abf242aa`. Readable `/boot`,
Wayland/QPainter and unchanged resident enrollment remain established.
The combined left-USB/capacity overlay is `left-usb-trial-01`; new package
builds retain that accepted both-left graph and validate inherited resources. The older kit `update-c1934fe10df6` remains rollback.

Owner reports TONOR USB microphone, drawing tablet through a powered hub and
AirPods Max USB audio working. Kernel logs corroborate TONOR `snd-usb-audio`
and hub enumeration; tablet identity and audio quality are unqualified.
Left-rear hub charging is supported by owner report and battery telemetry in
one arrangement; general USB-C charging and role swaps remain unqualified.
Built-in HDMI and USB-C display output still fail; only the internal DRM
framebuffer connector is exposed.

## USB and storage

The right controller is `392280000.usb`, limited to `high-speed` USB2. The
YubiKey enumerated at 12 Mbit/s as `1050:0407`, with both HID interfaces bound.
A root hub advertising 10 Gbit/s does not establish a USB3 connection.
The USB integration and retained upstream basis are described in
[patch provenance](usb-patchset-provenance.md).

NVMe requires m1n1's checked ANS firmware handoff and the inherited live
`/chosen/arch-m4,ans-handoff` marker. The default `make boot` loader supplies
that handoff; the `boot-safe` variant does not. Linux remains on SD in both
cases. Enumeration does not justify mounting or writing internal macOS
filesystems as a diagnostic step.

## CPU and cooling

| Domain | Saved logical CPUs | Policy range |
| --- | --- | --- |
| First P cluster | `0,5,6,7` | 1.260–4.512 GHz |
| E cluster | `1,2,3,4` | 1.020–2.592 GHz |
| Second P cluster | `8,9,10,11` | 1.260–4.512 GHz |

CPU numbering is discovered from MIDRs, not assumed. The current provisional
DT weights P=1024/E=864 normalize to accepted runtime P=1024/E=496. A first controlled-placement pair improved
single-core Geekbench 7 from 1,634 to 2,489 with P-only affinity; it does not
establish calibrated capacities or a permanent desktop policy.
See [CPU experiments](cpu-performance.md). The sampled busy events worker is
DRM XRGB8888 → XRGB2101010 conversion/copy, with 51 of 64 sample IPs in the
conversion routine. The paired scalar candidate is compiled/tested offline
but has not been installed or measured on the desktop.

Two short local P-core SHA256 runs requested 4.512 GHz while the driver's
current-state readback sampled 3.924 GHz; E-core readback reached 2.592 GHz.
That gap needs T6040 status/OPP decoding review before attributing it to
throttling. The repeatable 1.52 crypto throughput ratio is not a general
scheduler capacity calibration. Earlier captures appeared to show fan response, but a later 491-sample
capture froze every temperature, actual RPM and target value. Firmware cooling
ownership and telemetry freshness require raw-read diagnosis.

Keep `idle=nop arm64.nowfxt`: T6040 safe WFI/WFIT support remains unresolved.
Spinning idle CPUs consume power and thermal headroom. Do not re-enable
fused-off CPUs or remove these boot arguments to chase benchmark scores.

Reported P-domain sensor peaks reached 114.25°C with fan peaks around
2,400–2,600 RPM. SMC key labels are not calibrated mappings to individual
cores; these readings require read-only investigation before governor or fan
experiments. Manual fan control is disabled by default and is not qualified.
An earlier macOS capture reported mode 3; a later bounded capture returned
mode 0 on both fans while actual RPM changed. The Linux manual mode uses 1;
successful sysfs exposure does not establish safe ownership transitions.
[Key availability](evidence/2026-10-05-j614s-smc-keys.json) and
[native captures](evidence/2026-10-05-native-return.json) retain the evidence.

## Useful native checks

```sh
uname -r
lsblk -o NAME,TYPE,SIZE,FSTYPE,MOUNTPOINTS
lsusb
sudo m4rch-power-report --runtime
sudo m4rch-driver-diagnostics --output /boot/driver-diagnostics.txt
wpctl status
```

Use root for protected hardware clock readings; `scaling_cur_freq` and
time-in-state normally describe requested states rather than sustained clocks.
The diagnostic kit collects kernel, Type-C/USB, input, audio and power evidence
without authenticating a token, recording audio or forcing hardware controls.

Use `sudo systemctl poweroff` for storage shutdown. Physical power-off has
not been qualified by the latest capture. If the machine remains on, wait
for filesystem teardown to complete before using the power button. Suspend
targets and lid-triggered sleep remain disabled.

The [round-five receipt](evidence/2026-10-05-native-round5.json) accepts the
optimized framebuffer kernel and retained USB/capacity graph. Informal worker
samples suggest reduced conversion cost, without a controlled speedup claim.
Fresh raw sensors rule out a consistently reproduced hwmon freshness failure;
boot-dependent fan modes and a stopped benchmark make cooling the next focus.

The [round-six receipt](evidence/2026-10-06-native-round6.json) verifies fixed
cycle/instruction probes on P0, E and P1 with restored controls. Full perf
registration and maximum-clock qualification remain pending. Cooling changed
within one boot, so the next capture traces its timing rather than repeating
a boot matrix.

Round seven recorded a Linux SD cache-flush error-84 and block I/O error,
with ext4 errors_count0and verified return files. This neither establishes
filesystem corruption nor certifies the medium; investigate the flush/host
path independently before repeated update or storage-stress work.

The owner confirms USB and Bluetooth audio working. This does not establish
internal microphone/camera support. The J614s ADT labels speaker amplifiers
`audio-control,sn012776`; protection settings from another model are not
qualification for this machine. macOS discovery did not activate capture or playback.

GPU work now targets Gravity's G16 implementation. This machine reports G16S,
two clusters and sixteen enabled cores. See the
[GPU bring-up scope](../experiments/t6040-gpu/README.md) and
[captured contract](evidence/2026-10-06-gpu-contract.json). The identification
patch is not active in the maintained kernel; firmware/render-node bring-up
and Mesa G16S support remain unverified.
