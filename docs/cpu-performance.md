# CPU support

> Historical trial commands and diagnostic paths in this record may have been retired.
> See the [documentation index](README.md) for preserved source archives and
> the current setup; do not treat trial boot paths as current recovery instructions.

The current three-cluster cpufreq driver already scales: P policies expose
1.260–4.512 GHz and the E policy 1.020–2.592 GHz. The accepted capacity overlay gives
runtime P=1024/E=496 across all twelve live cores. Requested frequencies are not sustained physical-clock proof.

## Maintained SME and shallow idle

**Current 7.3.0-m4rch kernel:** The older board-specific `SavedWFI` cpuidle
patch and its `cpuidle_apple.saved_wfi` parameters are not present. Aurora's
arm64 idle path instead detects M4-or-later Apple cores and preserves registers
around WFI; it also saves and flushes FP/SIMD state before entering WFI. The
current boot command line uses `idle=wfi arm64.nowfxt`. On this machine the
Apple cpuidle driver exposes two WFI entries, both using that arm64 idle path.
The boot log confirms that register preservation was enabled. This describes
the running diagnostic kernel; the newly built main package contains the same
Aurora idle implementation but has not yet been boot-tested.

The following paragraphs describe the earlier 7.1.3-based implementation and
its testing; they are not the configuration of the current 7.3.0 kernel.

The normal `linux-m4rch` build enables ARM64 SME/SME2 support and registers
one default-enabled SavedWFI state on J614s/T6040. The state explicitly saves
and restores x0–x30 around one WFI; this is not hardware state retention or
qualified deep sleep. Other Apple machines retain their existing idle path.
Suspend remains unqualified and disabled. No clock or voltage limits change.

```sh
cat /sys/module/cpuidle_apple/parameters/saved_wfi
cat /sys/module/cpuidle_apple/parameters/saved_wfi_progress
echo 0 | sudo tee /sys/module/cpuidle_apple/parameters/saved_wfi
```

For next-boot disable, add `cpuidle_apple.saved_wfi=0` to the GRUB Linux command
line. Keep `idle=nop arm64.nowfxt`. Package revision 7.1.3-2 integrates this
path; its combined build still needs native verification after installation.
Earlier returns tested the save/restore path and SME workers on all twelve cores.
The SME-only signal-frame adaptation fixes userspace test assumptions, not
kernel state handling. Ordinary SVE remains unavailable on this hardware.

The sections below preserve the development evidence and earlier trial names;
they are not additional steps required to enable the maintained features.

## Evidence

| Geekbench 7.0.0 Preview, Linux AArch64 | Single | Multi |
| --- | ---: | ---: |
| [All twelve cores](https://browser.geekbench.com/v7/cpu/555966) | 1,634 | 12,446 |
| [Eight P cores](https://browser.geekbench.com/v7/cpu/556006) | 2,489 | 12,646 |

Both captures used AC, the existing X11 desktop and unchanged `schedutil`.
The 52.3% single-core difference supports further placement testing. One
sequential pair with unequal starting temperatures/background load cannot
establish a calibrated E/P ratio, repeatable gain or permanent affinity policy.
P-only multicore also has eight eligible CPUs rather than twelve. The
[evidence receipt](evidence/2026-10-05-native-return.json) records these limits.

Saved numbering: P0 `0,5,6,7`, E `1,2,3,4`, P1 `8,9,10,11`. The helper discovers
MIDRs and policy membership; do not assume CPU0 is E or use `4-11` as the P mask.
Keep all twelve cores enabled for ordinary use.

## Capture clocks and cooling first

The previous P-only run reported a `Tp0Y` peak of **114.25°C** and modest
automatic fan response. Key labels are not calibrated core-temperature
identities. Check sensor interpretation, clock visibility and cooldown before
another sustained benchmark or a governor experiment. Do not force fan
control, frequency bounds or unsupported idle states to compensate.

```sh
make cpu-tools
```

Copy the printed `out/sdboot/cpu-tools-ID/` directory to the actual mounted
ARCHBOOT partition, using the mount checks in [setup](setup.md). No kernel
install, reflash or enrollment is needed. Inside Linux, set its actual path:

```sh
kit=/boot/cpu-tools-ID
sudo python3 "$kit/m4rch-cpu-benchmark" --inspect
sudo python3 "$kit/m4rch-power-report" --runtime
sudo sh "$kit/run.sh" --cpus all \
    --output "$HOME/cpu-idle" -- sleep 60
```

Output directories must be new and reside on ext4, such as Alice's home.
The privileged parent reads protected clock attributes; workloads still run
as the invoking Alice account. `cpuinfo_cur_freq` is mode 0400 on this kernel:
an Alice-run null reading does not establish that the attribute is absent.
Compare a privileged read with the attribute's existence and access mode.

Keep `idle=nop arm64.nowfxt`. SavedWFI is a shallow state; counters prove
completed calls, not physical sleep depth or a calibrated power saving.
Follow the [native-agent follow-up](native-agent-followup.md) for the pending
post-boot checks and bounded cooling capture.

## Compare placement

After cooling is understood, use the same benchmark binary, desktop session,
power conditions, helper interval and comparable starting temperatures. Check
`./geekbench7 --help` for supported local-results/single-core options. A GB6
score is not a GB7 target. Public result uploads require separate authorization.

```sh
sudo sh "$kit/run.sh" --cpus all \
    --output "$HOME/cpu-default" -- ./geekbench7

# Cool to a comparable starting condition before the second run.
sudo sh "$kit/run.sh" --cpus performance \
    --output "$HOME/cpu-pcores" -- ./geekbench7
```

These commands make no governor change. Repeat/reorder comparisons rather
than treating one pair as calibration. A later single-P versus single-E
comparison can use explicit CPU lists after verifying live MIDRs. Snapshot
samples are not exact subtest-residency traces.

If a governor question remains **after cooling has been clarified**, compare
matched `--cpus p0` runs, then add `--governor performance` to one. The helper
changes only selected policies, retains frequency bounds and restores original
governors on success, failure, Ctrl-C or SIGTERM. SIGKILL/power loss cannot
run cleanup; saved metadata records original settings. An all-core performance
governor also raises clocks on spinning idle cores and is not a default.

Captures contain `metadata.json`, `samples.jsonl` and `summary.json`, including
affinity escapes, clocks, sensors, fans and AC state. Return captures and
benchmark output, not only a score:

```sh
sudo tar -czf /boot/cpu-results.tar.gz -C "$HOME" cpu-default cpu-pcores
```

Measured T6040 E/P capacity descriptions may eventually improve scheduling
from the SD side. Base-M4 or other-chip ratios are not calibration. Overlays
must target only live CPUs after m1n1 prunes fused-off nodes. No permanent governor or replacement idle workaround is installed.

The owner-authorized next-boot trial now adds SD-only DT weights P=1024/E=864
for this machine's twelve live CPUs. Pinned `arch_topology` multiplies weights
by each policy's maximum frequency, predicting runtime P=1024/E=496.
These provisional weights use short integer throughput measurements below
CoreMark's official minimum duration; they are not calibrated silicon DMIPS.
The [validation receipt](evidence/2026-10-05-capacity-trial.json) records the
offline merge. Round-five native acceptance passed; a controlled speedup remains unverified. The previous
SD overlay and restore script are retained in `/boot/capacity-trial-01`.

Round five observed occasional requested4512/status3924MHz on both P clusters.
The driver decodes a state index through the OPP table; hardware PMU counters
were unavailable. A constant physical3.924GHz cap is not established. Raw CPU
temperatures were fresh, but boot-dependent fan state and a benchmark stopped
at a sensor100.328°C keep sustained testing deferred. See the
[round-five receipt](evidence/2026-10-05-native-round5.json) and HANDOVER.

## Current clock evidence

The [round-seven receipt](evidence/2026-10-06-native-round7.json) records 28
independent fixed-count probes during an owner-authorized workload. Both P
clusters reached approximately 3.924 GHz in sampled windows, including a
requested 4512/status 3924 MHz pair. This supports a real discrepancy during those
windows; short successive readings do not prove an absolute clock ceiling.
`btop` reads request-facing scaling_cur_freq and cannot resolve the discrepancy.

The 100°C monitor stop was an agent-selected experimental bound, not a verified
M4 Pro throttle threshold. Raw sensor/hwmon agreement verifies decoding, not
physical sensor location or safe limits. Match the same named channels under
macOS with thermal-pressure/frequency context before selecting further Linux
load guards. Preserve the owner's observed steady ~2600 single-core improvement
without attributing all of it to a single change.

## macOS comparison

The same machine on AC scored [3320 single / 21988 multicore](https://browser.geekbench.com/v7/cpu/559215/)
with Geekbench 7.0.0 and CPU/thermal telemetry. Across 287 complete samples,
macOS reports peak active P-cluster frequencies of 4475/4510 MHz and nonzero
4512 MHz residency in 83/141 samples. Samples with at least 80% cluster active
residency reached 4434/4510 MHz. Thermal pressure remained Nominal.
See the [comparison receipt](evidence/2026-10-06-macos-cpu-comparison.json).

This strengthens the clock investigation: macOS uses states above the
approximately 3924 MHz found by Linux's independent probes. These interfaces
are not identical measurements; an absolute Linux ceiling and its cause remain
unproven. Individual SMC channels can return exact 40°C or implausibly low
values on macOS. Nominal pressure does not calibrate those channels. Both fan
modes 3/zero RPM and 0/positive RPM occur on macOS.

The former cpufreq snapshot diagnostic
captures command/status/OPP decoding inside the owning driver, without voltage,
PLL or fan-control changes. The next-boot kit includes matched packages and
accepted rollback; [HANDOVER.md](../HANDOVER.md) specifies one native session. macOS
also records deep P-cluster down residency; Linux's retained idle safeguards
make proper idle a separate power/thermal-headroom investigation. No benchmark
score gain from implementing either change is established yet.

## Command/status result and next implementation

[Round eight](evidence/2026-10-06-native-round8.json) independently validated
180 raw snapshots. One P0 command reached state19 (4512 MHz); decoded status
stayed at state14 (3924 MHz) before and after a fixed-counter sample estimating
3.922 GHz. Cleanup passed. CPU8 never requested a high state in this capture.
The observations are successive, not atomic, and do not prove an absolute cap.

The pinned m1n1 payload already calls `cpufreq_init()` before starting
secondaries and handing off to U-Boot. T6040 enables only ADT-selected APSC and
fixed-frequency PLL relock features; older throttle/misc offsets are deliberately
excluded after SErrors. No verified missing boost-enable register was found.
Adding another initialization call or importing those older offsets is not a fix.

Idle is the next source-level investigation. `CONFIG_ARM_APPLE_CPUIDLE=y` is
already set, but the pinned driver does not match T6040. Its shallow path uses
`cpu_do_idle()`, which retains the nop fallback; its deep path saves callee-saved
registers, invokes CPU PM notifiers and touches an Apple system register around
WFI. Register accessibility and full T6040 restoration remain unqualified.
Simply adding a compatible string would bypass that qualification.

Asahi's [M4 idle explanation](https://asahilinux.org/2026/08/progress-report-7-2/)
describes state loss on WFI and the need to save state. Its
[PSCI-via-EFI proposal](https://github.com/AsahiLinux/m1n1/pull/618) is another
implementation path requiring firmware/runtime integration. Spinning cores are
a plausible boost constraint, not an established T6040 cause. Qualify the
state-saving path before a guarded, reversible idle trial. No further clock
capture or benchmark is needed to repeat the result above.

The [returned idle audit](evidence/2026-10-06-idle-audit.json) confirmed no native
idle driver/states and supplied a default-off candidate. The owner authorized
a first bounded experiment without requiring full retention qualification.
The [built trial](evidence/2026-10-06-t6040-idle-trial.json) restricts activation to
J614s/T6040 using `cpuidle_apple.experimental_t6040_idle=1`; the existing deep
sequence is unchanged. Both GRUB entries retain the nop/WFxT safeguards.
Separate trial images preserve normal boot and do not require package replacement
or enrollment. The first native trial produced an undefined-instruction Oops
on CPU4 around 0.11 seconds, before a visible PC/backtrace, then rebooted.
The [follow-up](evidence/2026-10-06-t6040-idle-trace.json) limits deep entry
to one attempt on CPU4, brackets the original
register/WFI sequence with checkpoints and prints the saved exception frame
before the ordinary dump. It aims to locate the fault, not enable useful idle
or establish a performance gain. See the
retired trial notes for the historical selection and rollback procedure.

The traced native run reached stages 1–4, then faulted at
`ffffc000810dcdb0`: `msr s3_5_c15_c5_0, x0` in the exact linked kernel.
The preceding read returned zero. WFI was not reached. This identifies the
initial control-register write as the immediate blocker; it does not demonstrate
a wake-state retention failure or prove the register is locked. A T6040 idle
path must address this incompatibility before wake/retention tests are useful.

The [saved-WFI candidate](evidence/2026-10-06-t6040-saved-wfi.json) bypasses
the incompatible control-register accesses. It saves x0–x30, executes one WFI
on CPU4, and restores the frame before returning into C; existing FPSIMD
notifiers remain. Other cores and subsequent idle calls use nop. It is a
bounded test of this alternate entry path. The native return confirmed stage6,
CPU_PM_EXIT completion and exactly one CPU4 deep-state entry, with normal
owner-reported input/USB/desktop behavior. Repeated wakes and P-core coverage
remain untested. The trial image disappeared from the ESP before native kit
verification; the agent preserved read-only evidence after the collector guard
stopped. This boot therefore qualifies the wake result, not installed-kit
integrity or sustained idle enablement.

The [bounded saved-WFI batches](evidence/2026-10-06-t6040-wfi-batches.json)
passed 32 wakes on CPU4 and CPU5, with 512 successful user register-state sleep
checks and no new fault/warning matches in the journal delta. The owner chose a direct
continuous all-core trial next, retaining normal boot rollback. Its saved
assembly is unchanged; an explicit runtime switch enables unlimited concurrent
entries. The native return passed sustained all-core idle and 1,536 user register-state
sleep checks with no new fault/warning matches. Power savings, wake latency and
long-duration reliability remain unqualified; the next same-boot comparison
toggles continuous WFI while capturing whole-machine battery telemetry.

The next shallow-state candidate removes the inherited10ms selection threshold
that left short predicted gaps on nop. It retains the saved sequence and exposes
one opt-in shallow state; latency is provisional. The power comparison and
benchmark can run on this candidate in one boot, with the previous working
continuous kernel retained for rollback.
