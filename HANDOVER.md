# m4rch native capacity trial

The owner authorized this provisional capacity-only trial for the next boot.
The SD `/dtbs/board.dtbo` now gives eight P CPUs DT weight 1024 and four E CPUs
864. The pinned kernel's maximum-frequency normalization predicts runtime
P=1024 and E=496. These are trial placement weights fitted to short integer
measurements, not calibrated silicon DMIPS values or a promise of speedup.

Offline dtc/fdtoverlay validation changed exactly twelve capacity properties
and confirmed every target against the live native CPU paths/classes. Kernel,
initramfs, GRUB, resident loader, clock tables, governors, idle workarounds,
USB resources and fan ownership are unchanged. No re-enrollment is required.

## Verify this boot

Use Alice's terminal. This kit has a read-only acceptance helper:

```sh
kit=/boot/cpu-tools-160e4b73d015
capture="$HOME/m4rch-capacity-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -m 700 "$capture"
python3 "$kit/m4rch-verify-capacity" > "$capture/capacity.json"
sudo sh "$kit/collect.sh" snapshot --label capacity-boot --output "$capture/baseline"
```

Read the JSON even if the helper exits nonzero. It requires all twelve CPUs,
correct MIDR classes and DT values, runtime P=1024/E=496, and unchanged maximum
frequencies. If all remain 1024, inspect DT application, capacity parsing and
cpufreq notifier completion before benchmarking. Include new dmesg warnings.
The older package names remain expected until the owner chooses migration.

If acceptance passes, run one bounded, unpinned local CPU workload and record
where its executing thread spends time. Use the same workload/source/compiler
as the prior comparison; capture before/after temperatures, AC and background
load, and report placement without promising exclusive P-core residency.
Keep all twelve cores online. Do not change clocks, governors or cooling.

## Rollback

The saved previous overlay and a hash-guarded restore script are in:
`/boot/capacity-trial-01`. Restore from native Linux with:

```sh
sudo sh /boot/capacity-trial-01/rollback.sh
sync
```

Then reboot normally. The rollback script only replaces the SD overlay.
From macOS, if Linux cannot boot, use the correctly mounted SD ESP:

```sh
cp /Volumes/ARCHBOOT/capacity-trial-01/board-before.dtbo /Volumes/ARCHBOOT/dtbs/board.dtbo
sync
```

Use macOS Eject or `diskutil unmountDisk` before rebooting/removing the card.
Do not rerun an older package kit's install script during this isolated trial:
it may restore a previous overlay and mix changes. Preserve both artifacts.

## Source and remaining investigations

`capacity-trial-01` includes the exact source, validation receipt and pinned
arch_topology/arm64 topology source. The generic capacity code multiplies raw
DT weight by cpuinfo.max_freq after all CPU policies register, then normalizes
and rebuilds scheduler domains. AMU configuration alone does not establish
active frequency invariance. The earlier source-review packet remains on SD.

Keep the 4.512 GHz request / 3.924 GHz status gap unresolved pending independent
T6040 status/clock validation. The CPU driver's current-state readback is an
OPP lookup, not an independent measured oscillator frequency. Software boost
gating did not explain the gap in the return: top P OPPs were available and
not marked turbo. Do not probe older chips' throttle registers.

The return also caught an events worker using roughly half a core over five
seconds; the callback was not identified. If it recurs, capture the executing
workqueue callback. The retained kernel config has FTRACE disabled but
PERF_EVENTS enabled, so start with the five-second software CPU-clock sampler:

```sh
cc -O2 -Wall -Wextra "$kit/m4rch-worker-sampler.c" -o "$capture/worker-sampler"
# Set worker_pid to the current busy kworker PID found from interval CPU deltas.
# sudo "$capture/worker-sampler" "$worker_pid" "$capture/worker-samples.jsonl"
sudo cat /proc/kallsyms > "$capture/kallsyms.txt"
```

The sampler requires a kworker PID, uses a private perf fd/ring and caps output.
Resolve sample IP/callchain addresses against same-boot kallsyms and count the
hot functions; exclude perf context-marker values. This may fail if software
sampling/unwinding is unavailable: retain the exact error and do not rebuild
or weaken kernel restrictions just to make it run. Native sampling is untested.
The kallsyms capture contains privileged addresses; keep it private in the return.

## Complete this session before returning

Do capacity acceptance first, then gather the busy-worker trace and short
placement/clock/cooling captures in the SAME boot. Runtime diagnostics, bounded
tracing and workload compilation do not require re-enrollment or reboot. If a
worker can be traced to a particular driver, inspect its supplied source and
return a concrete candidate fix, not only another request to collect logs.
Do not install a speculative driver or switch several policies at once.

`/boot/session-source-context` supplies pinned scheduler/AMU and
workqueue context. Read it locally rather than spending the session resolving
network fetch failures. Mark unresolved register semantics as unresolved;
ordinary sysfs status readback still is not independent clock measurement.

macOS attachment captures now independently map left-front to usb-drd1
(controller 0x38a280000) and left-rear to usb-drd0 (0x382280000). Both showed
the owner's drive at a reported 5 Gbit/s in macOS. See `/boot/usb-socket-map-20261005`
for filtered ancestry captures and a summary; this is not Linux USB3 support.
The hpm0/hpm1 assignments still rely on the ADT associations, not a separate
PD attachment-state capture. Left-specific transport/repeater validation remains. Keep the working right port and AC unchanged.
Do not enable left nodes as passive discovery. Keep NOP idle/hotplug safeguards.

## Return and filesystem recovery

Both incoming kits had the same helper restored from a recovered FAT filename,
with exact manifest hash matches. That recurrence is real but its cause is
undetermined. Preserve recovered files; do not repair or reflash the card.
The macOS agent saves rollback and verifies read-back, then unmounts the SD
cleanly. Report whether the next kit arrives intact without another recovery.

Write your own `$capture/HANDOVER.md` with capacity acceptance, workload
placement, temperatures/background work, changes and rollback status, then:

```sh
stamp=$(date -u +%Y%m%dT%H%M%SZ)
sudo sh "$kit/collect.sh" bundle --input "$capture" --output "/boot/m4rch-return-$stamp.tar.gz"
sync
```

## Both-left USB2 trial in this visit

Charging stays on MagSafe. The owner authorized trying both left ports.
Finish the capacity/worker measurements above, then proceed without a return
handoff to macOS. `/boot/left-usb-trial-01` holds the combined capacity + left
USB overlay, validation, source and a guarded activation/rollback helper.
Its `deployment.json` identifies the exact matching pacman update directory.
Install the matching kit with `sudo sh /boot/update-a622abf242aa/install.sh`,
following its own rollback instructions. This migrates the old package names to m4rch names. Keep the
working old kernel/module/boot rollback kit `/boot/update-c1934fe10df6`; its
kernel payload matches the currently booted SD image. Save the current ESP
boot files before installation. Do not remove the old kit to save space.

After the install has completed successfully:

```sh
sudo python3 /boot/left-usb-trial-01/activate.py activate
sync
sudo reboot
```

The helper refuses a different SD ESP, unexpected overlay, mismatched kernel
image, or missing matching kernel/modules provenance. One ordinary Linux
reboot is needed to load this driver and device tree. Do not force-load modules
built for a different running kernel. The resident m1n1/U-Boot bytes stay fixed.

This adds a0 SPMI, HPM0/HPM1, two USB2 PHY providers, four DARTs, and the two
controller/connector graphs. The driver now prioritizes explicit cable events
over inherited forced-device mode. Right USB and the capacity weights remain
unchanged. USB3, Thunderbolt, USB-C charging and role swaps are outside this
trial. macOS confirmed physical drd socket mapping; the PD-to-socket mapping
is provisional from ADT port numbers. PHY sequencing on these left instances
is unverified. Log probe failures before changing transport or PHY registers.

On the new kernel, collect `uname -r`, `pacman -Q linux-m4rch config-m4rch`,
`journalctl -b -k`, `systemctl status m4rch-usb.service`, `lsusb -t`, and the
collector snapshot. Test each left socket separately with YubiKey first,
both orientations, boot-connected and reconnect; record LED and enumeration.
Then try the thumb drive, both orientations, and only an explicitly created
scratch file for transfer/hash testing. Repeat the right-port smoke test.
Use kernel USB/Type-C messages and `/sys/class/typec` to distinguish PD attach
from role-switch/PHY/controller failures. Do not infer enumeration from hubs.

If either left path hangs or disrupts the working right port, restore the
capacity-only overlay, retaining the newer kernel for diagnosis:

```sh
sudo python3 /boot/left-usb-trial-01/activate.py rollback
sudo reboot
```

If Linux cannot start, macOS can restore the saved capacity overlay from the
mounted ESP's `left-usb-trial-01/board-capacity.dtbo` to `dtbs/board.dtbo`.
The package update's separate rollback is needed to restore the old kernel.
Return CPU results and both USB trials together, including failed tests.
