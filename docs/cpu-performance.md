# CPU experiments

The current three-cluster cpufreq driver already scales: P policies expose
1.260–4.512 GHz and the E policy 1.020–2.592 GHz. Every live core currently
advertises scheduler capacity **1024**, so Linux lacks an E/P capacity
description. Requested frequencies are not sustained physical-clock proof.

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

Keep `idle=nop arm64.nowfxt`. T6040 safe CPU sleep is unresolved, so an idle
timeline still includes spinning cores rather than deep-idle measurement.
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
offline merge. Native acceptance and speedup remain unverified. The previous
SD overlay and restore script are retained in `/boot/capacity-trial-01`.
