# m4rch native work

Work on the running **J614s / T6040** installation. This is a bidirectional
handover: inspect, run bounded tests, then return a new `HANDOVER.md` and raw
evidence on the SD ESP. Do not overwrite this incoming file with the return.

## Current facts

- The owner reports no recurrence of the earlier ext4 incident through
  repeated shutdowns and reboots. Record new failures if any; storage is not
  the current investigation priority.
- Right-port USB2/YubiKey enumeration, reconnect and authentication work.
  Left ports are disabled in the current hardware description.
- Twelve CPUs run with `schedutil`; all advertised capacity values were 1024.
  One X11/AC benchmark pair gave 1,634 single-core with all CPUs versus 2,489
  with P-only affinity. That is a placement hypothesis, not capacity calibration.
- Prior sensor capture peaked at 114.25 C. Sensor interpretation and sustained
  root-readable clocks remain to be checked before stronger load tests.
- The owner will handle migration to the new m4rch packages and native desktop
  checks. Verify what actually booted rather than assuming migration completed.

## Start and capture

The kit contains `collect.sh`, `m4rch-native-lab`, the existing benchmark and
power helpers, checksums, and setup instructions. No helper loads drivers or
writes sysfs, fan controls, governors, registers or boot arguments by default.
Run in Alice's terminal, using the kit directory beside this file:

```sh
kit=/boot/cpu-tools-ID       # replace ID with the actual incoming kit
capture="$HOME/m4rch-native-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -m 700 "$capture"
sudo sh "$kit/collect.sh" snapshot --label baseline --output "$capture/baseline"
```

The collector checks the kit and records USB/Type-C state, selected live DT
properties, driver bindings, kernel configuration/logs, CPU topology, clocks,
idle states, thermal readings and fan data. Snapshots are root-owned/private;
use sudo to inspect them. Missing commands and failed probes are evidence.
Use `instructions.md` for setup and `native-agent-followup.md` for mount/session
checks. Keep Alice Admin/alice, hostname t6040 and the requested login policy.

## USB2

Use the YubiKey and the available USB-C thumb drive. Name physical left ports
`left-front` (toward the trackpad) and `left-rear` (toward the hinge). For each
device/port, capture unplugged, connected in each orientation, and disconnected
again. Wait about five seconds after each cable action. Example:

```sh
sudo sh "$kit/collect.sh" snapshot --label right-key-normal --output "$capture/right-key-normal"
sudo sh "$kit/collect.sh" snapshot --label right-key-flipped --output "$capture/right-key-flipped"
sudo sh "$kit/collect.sh" snapshot --label right-key-disconnected --output "$capture/right-key-disconnected"
```

Record LED/power, `lsusb -t` negotiated speed, driver binding, and whether HID
access works as Alice. Let the owner exercise authentication without logging
credentials. Repeat a few reconnects. Mark unavailable hubs/adapters as untested.
For thumb-drive I/O, have the owner identify a disposable test filesystem and
use a new test file there; do not write raw disks or internal macOS partitions.
Report the device, byte count, elapsed time and read-back checksum.

Left-port observations will probably show no host: disabled nodes explain that
and do not prove an electrical failure. Inspect the live DT and pinned Wallace
USB2 provider before proposing left-port enablement. The optional
`macos-port-map.json` supplies freshly observed IODeviceTree resource/routing
metadata for comparison. Its ADT bytes are little-endian; do not parse them as
Linux DT cells. It contains no firmware, tunable sequences or owner records.
Map each controller, PHY
bank, DART, power domain, PD/SPMI transport and connector endpoint separately.
Do not copy the right port's addresses into a left-port node. Return a concrete
source patch or the exact missing evidence; preserve the working right port.

## Idle

Keep `idle=nop arm64.nowfxt` for this round. The cached current configuration
already has `CPU_IDLE`, `ARM_PSCI_CPUIDLE` and `ARM_APPLE_CPUIDLE` enabled.
In pinned Linux `e9d2237cd064`, `drivers/cpuidle/cpuidle-apple.c` excludes
T6040; its fallback state calls plain WFI. Adding T6040 to that list alone
would expose the state-loss problem we currently avoid.

Compare the running driver's states/config/DT with that source. Audit state
save/restore, fallback and hotplug/secondary CPU parking before suggesting a
candidate. Capture EFI availability, PSCI nodes/method and any idle-state DT
description. The PSCI-via-EFI RFC spans kernel, resident m1n1 and firmware
handoff; it is not a kernel-only switch and would require a new enrolled bridge.
Its example DT is T8103, so it does not establish T6040 support.

Primary references (resolve and record exact revisions when using branches):

- [Asahi idle source](https://github.com/AsahiLinux/linux/blob/asahi/drivers/cpuidle/cpuidle-apple.c)
- [PSCI-via-EFI RFC](https://lists.openwall.net/linux-kernel/2026/07/08/539)
- [m1n1 experiment](https://github.com/AsahiLinux/m1n1/tree/psci-via-efi)
- [Kernel experiment](https://git.kernel.org/pub/scm/linux/kernel/git/sven/linux.git/log/?h=efi-psci)

Return a compatibility assessment and bounded candidate plan. Do not activate
untested WFI states or remove the idle workaround during the evidence run.

## Scheduling and cooling

First take an unchanged 60-second idle capture on AC:

```sh
sudo sh "$kit/run.sh" --cpus all --output "$capture/cooling-idle" -- sleep 60
```

Verify `cpuinfo_cur_freq` as root, MIDRs, policy membership, capacity values,
sensor labels/units, fan targets/RPM and AC state. Keep the current governors,
frequency limits and fan ownership. Stop sustained workloads if cooling looks
abnormal or temperatures keep rising; return that evidence rather than tuning.

After interpreting cooling, inspect the installed Geekbench binary's `--help`
for local-result/upload controls. Use a local-only run or obtain the owner's
authorization for public submission. Run the same single-core workload on one
verified P CPU and one verified E CPU, repeat in reverse order after cooling,
and retain monitoring output. Select explicit CPU IDs discovered with:

```sh
python3 "$kit/m4rch-cpu-benchmark" --inspect
# Substitute a verified CPU ID and actual local-only workload invocation:
# sudo sh "$kit/run.sh" --cpus CPU --output "$capture/p-single" -- WORKLOAD
```

Do not calibrate scheduler capacities from aggregate Geekbench scores. Compare
matched per-workload throughput and clocks, then propose a measured SD-side
capacity description with rollback. Keep all twelve CPUs for ordinary use.

## Return

Write `$capture/HANDOVER.md` with the running versions/source commit, actual
mount/session, USB matrix, idle findings, clock/cooling observations, exact
changes and rollback, and the next patch or missing evidence. Distinguish
executed tests from proposals. Include config/source diffs; keep firmware,
disassembly and credentials out of the return bundle.

```sh
stamp=$(date -u +%Y%m%dT%H%M%SZ)
sudo sh "$kit/collect.sh" bundle --input "$capture" --output "/boot/m4rch-return-$stamp.tar.gz"
sync
```

The archive refuses existing output paths and symlinks. Publish only after
the command succeeds. Keep the captured originals until the macOS agent has
read the return. Do not change the enrolled loader for a routine SD update.
