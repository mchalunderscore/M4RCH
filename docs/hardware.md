# Hardware status

Target: **14-inch M4 Pro MacBook Pro, Mac16,8 / J614s / T6040**.
Native evidence currently covers a 12-core, 24 GB machine. This is an
experimental configuration, not certification of every device or workload.

| Device or function | Established behavior | Remaining work |
| --- | --- | --- |
| SD boot/root | Full m1n1 → U-Boot → SD GRUB → Linux boot; persistent ext4 and first-boot expansion | An earlier intermittent ext4 I/O incident remains unexplained |
| Internal display | Software-rendered KDE/X11, Firefox and compositing | Wayland/QPainter is configured but awaits a native session check; no GPU acceleration |
| Keyboard, trackpad, lighting | Native input and keyboard lighting have worked | Broader gestures/haptics and regression coverage |
| Wi-Fi | Connection, routing and traffic | Roaming and long-duration reliability |
| Bluetooth | Mouse input and AirPods Max A2DP playback | Headset microphone/duplex audio and broader devices |
| Right USB-C | USB2 YubiKey 5C HID enumeration, unplug/replug and user-tested authentication | Other devices, hubs, both plug orientations and sustained high-speed transfers |
| Left USB-C, USB3, Thunderbolt | Disabled in this implementation | Platform and PHY/host support |
| Internal NVMe | Namespace/partition discovery and reads through the ANS-aware loader | Writes, sustained I/O, failure recovery and shutdown qualification |
| CPU | Twelve cores online; three scaling policies using `schedutil` | Correct E/P scheduler capacities, safe idle, thermal/power qualification |
| Fans/temperatures | SMC RPM, targets, limits and temperature keys exposed | Sensor interpretation and automatic-cooling behavior under sustained load |
| Power | Battery/AC reporting and storage teardown | Battery energy decoding, physical shutdown/reboot qualification, suspend |
| Internal audio, camera, brightness, external displays | No established functioning path | T6040/laptop support |

The known-good native package kit is `update-c1934fe10df6`; its
[captured identifiers](evidence/2026-10-05-native-return.json) predate the
naming cleanup. Those results do not establish that a newly edited kernel
has passed hardware tests.

New builds use kernel release `7.1.3-m4rch` and packages `linux-m4rch`,
`config-m4rch`, `grub-m4rch` and `paru-m4rch`. The captured baseline above
predates that naming migration; its reported identifiers remain unchanged.

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

CPU numbering is discovered from MIDRs, not assumed. All live cores currently
advertise capacity 1024. A first controlled-placement pair improved
single-core Geekbench 7 from 1,634 to 2,489 with P-only affinity; it does not
establish calibrated capacities or a permanent desktop policy.
See [CPU experiments](cpu-performance.md).

Keep `idle=nop arm64.nowfxt`: T6040 safe WFI/WFIT support remains unresolved.
Spinning idle CPUs consume power and thermal headroom. Do not re-enable
fused-off CPUs or remove these boot arguments to chase benchmark scores.

Reported P-domain sensor peaks reached 114.25°C with fan peaks around
2,400–2,600 RPM. SMC key labels are not calibrated mappings to individual
cores; these readings require read-only investigation before governor or fan
experiments. Manual fan control is disabled by default and is not qualified.
macOS reported fan mode 3 while the Linux driver's manual mode uses 1;
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
