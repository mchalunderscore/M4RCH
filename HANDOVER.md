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
kit=/boot/cpu-tools-6a2e00da2410
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
workqueue callback with a short, narrowly filtered trace only after checking
available events and restoring any previous tracing state. Keep captured trace
data bounded. Establish this independently from the capacity change.

Left-port work still needs physical socket/PD correlation and left-specific
transport/repeater validation. Keep the working right port and AC unchanged.
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
