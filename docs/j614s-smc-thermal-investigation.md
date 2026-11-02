# J614s SMC and thermal investigation

2026-11-02. No-reboot investigation complete within the documented guards; maximum thermal budgets are not qualified. Hardware is a J614s MacBook Pro 14-inch M4 Pro,
running `7.3.0-j614s-pr1-ARCH`, based on Aurora Linux #795 head
`dc054fb02bfb002e41f2dd8f43a3dce2983cf537` with #804, #817 and #821 on
top (merge `c6af520e2920e3b5b2b604b23e89b2fcede369e3`). The normal
package-managed kernel entry has booted. Its J614s DT reuses the J616s sensor
and thermal descriptions.

## Upstream references

- [#507](https://github.com/aurora-silicon/linux/pull/507) explains the
  J616s SMC enumeration and sensor labels, and reports per-cluster load tests.
- [#715](https://github.com/aurora-silicon/linux/pull/715) merged the J616s
  thermal trips, energy model and CPU budgets. [#605](https://github.com/aurora-silicon/linux/pull/605)
  records the frequency-sweep method and measured rail mappings.
- [#511](https://github.com/aurora-silicon/linux/pull/511), folded into #533,
  states the GPU-zone policy was intended to shed CPU power at or above
  the GPU firmware's 101 C limit; its GPU benchmark comparison was pending.
- [#670](https://github.com/aurora-silicon/linux/pull/670) leaves fan policy
  with the SMC and supersedes the earlier host fan ladder. The current DT
  removes the active fan trips after defining them.
- The [kernel power allocator documentation](https://docs.kernel.org/driver-api/thermal/power_allocator.html)
  describes separate switch-on and desired-temperature passive trips.

## Key inventory

A temporary module calls the existing `apple_smc_get_key_by_index` and
`apple_smc_get_key_info` interfaces. The first inventory records key names,
types, lengths and flags only; it does not read arbitrary values or write SMC
keys. It returned 3,372 rows without lookup errors, with continuous indices and
strictly increasing unique key names. The raw metadata is kept root-only at
`/var/lib/m4rch/j614s-smc-thermal-20261102/smc-key-metadata.txt`.

Of the 480 distinct `apple,key-id` properties in the live SMC hwmon tree, five
temperature keys are not in this machine's inventory: `TDCR`, `TDEC`, `TF2S`,
`TPH3`, `TVm0`. The existing driver hides absent channels, so all 475 exposed
hwmon channel reads succeeded. This is not proof that all 475 channels have
accurate labels or calibration.

The table omits 34 readable, non-function, four-byte float keys in the T/V/I/P
groups: 31 T and 3 P. The temporary diagnostic sampled only these explicitly
listed T/P keys, after revalidating type, length, readability and non-function
flags. Across 336 snapshots during idle, CPU and GPU activity, four omitted
temperature keys varied: `TDTC` 28.81–30.81 C, `TSCP` 37.57–47.41 C, `TSG2`
41.33–52.14 C and `TVS3` 34.64–39.70 C. The other sampled keys were constant
in those windows; this does not prove that they are always placeholders or
limits. The boot journal records the five inherited keys as unavailable and
hides their temperature channels.

The retired sensor-table experiment against #795 dropped the five absent sensors
and added the four observable temperatures using generic SMC labels. Its
decompiled DT diff contained only those nine node changes; the 24 initial
thermal-zone sensor positions were retained.
The candidate DTB compiled without diagnostics. No claim is made about the
physical location of the added sensors.

The historical experiment branch is `codex/j614s-smc-sensors` at
`4d96c7d48405f63f070e26194efe282ba29c2639`, based directly on #795 head
`dc054fb02bfb002e41f2dd8f43a3dce2983cf537`. It changes only
`t6040-j614s.dts`. The exact #795 source and the candidate both compiled to
DTBs; a decompiled comparison shows precisely the five removals and four
additions, with no other tree changes. The normal DTS compiler emits existing
unit-address warnings for both trees; these are not introduced by the patch.
The patch is no longer carried in the active tree.

On 2 November a sensor-table trial was assembled from the installed PR-stack
sources, with only this nine-node sensor difference from the installed DTB.
The Aura and U-Boot payloads match the package-managed loader. The trial booted
successfully: all four added keys registered and read, all 475 previously
exposed labelled channels remained readable, no hwmon reads failed, and all 24
CPU/GPU thermal zones were present. The five absent keys produced no hwmon
unavailable messages. The exact standalone #795 branch was not separately
booted. The normal loader was restored and verified for the next boot; it is
also preserved at
`/boot/efi/m1n1/boot.bin.m4rch-before-smc-sensors` and in
`/var/lib/m4rch/smc-sensor-before-20261102T093853Z`. Private evidence is at
`/var/lib/m4rch/j614s-smc-thermal-20261102/smc-sensor-trial-a33b7471.json`.
The candidate uses the normal installed thermal policy, not
the separate GPU thermal experiment.

## Live measurements and limitations

All workloads use a high-priority watchdog that samples every approximately
0.25–0.29 s, checks every registered CPU/GPU thermal zone plus CPU Die Max,
and kills its workload at the configured threshold or on a read failure. The
initial 95 C threshold stopped one run at 96.3 C due to sampling interval and
temperature changes; subsequent measurements use a 93 C threshold. No fan
speed or fan mode was written. Private time-series are in
`/var/lib/m4rch/j614s-smc-thermal-20261102/`.

- The J614s has three CPU policies: P0 CPUs `0,5,6,7`, E CPUs `1,2,3,4`, P1
  CPUs `8,9,10,11`. Single P0/P1 loads raised the corresponding Tpx sensors and
  PR0b/PP0b rails; E load raised Tex sensors and PP2b. This supports the
  inherited mapping but does not validate every sensor label.
- Four E cores ran 90 seconds at a reported 2.592 GHz. During the last 30 seconds
  PP2b averaged 1.915 W, CPU Die Max averaged 67.8 C, fans were off, and E
  cooling state remained 0. The peak during the run was 81.1 C. This is not
  a measurement at a full-system thermal equilibrium or a validated budget.
- A 180-second two-P-core request hit the initial guard after ~109 seconds;
  peak CPU sensor 96.3 C, fans still off at cutoff. Over the last 30 seconds,
  PR0b averaged 3.60 W and PP0b 5.30 W. CPU frequencies were variable. Do not
  extrapolate these numbers into full-cluster or all-core sustainable power.
- A 60-second offscreen GPU workload completed with verified Mesa rendering,
  compute and readback. CPU/GPU-zone peaks were 83.4/68.5 C. A separate
  60-second GPU plus two-P-core workload also passed, with peaks 92.3/68.0 C.
  The SMC fans had started in the interval following the earlier CPU run;
  these observations alone do not identify which load caused the fan start.

## GPU-zone governor observation

All seven GPU zones report one passive trip at 101 C and a critical trip at
118 C. Their omitted `sustainable-power` is estimated at 4.62 W. An isolated
ftrace instance recorded `thermal_power_cpu_limit` events associated with GPU
zones while their sensors were about 57 C: e.g. the P0 cluster was allocated
around 8.6 W with a nonzero cooling state. The same trace showed no nonzero
allocations attributed to the CPU zones during that workload.

For a bounded A/B comparison, GPU zones alone were temporarily switched from
`power_allocator` to `step_wise`; all policies were verified restored on exit.
In the second comparison, with a single pinned P0 load, the allocator case had
nonzero P0 cooling state in 94.6% of samples and mean reported target/actual
CPU frequencies of 4.074/3.949 GHz; the step-wise case had state 0 and
4.490/3.975 GHz. Different temperatures and short duration limit the
performance comparison. The trace and reproduction establish a real policy
interaction, not a measured fixed performance penalty or the correct fix.
The source's allocator is always active with only one passive trip; upstream's
comments that GPU shedding only acts at 101 C therefore need rechecking.
A second isolated trace captured the PID inputs: for `gpu0-thermal` near
61.9 C, its estimated 4.62 W sustainable power and proportional term of
about 3.55 W yielded a power range of about 8.17 W, while the cooling actors'
combined maximum was about 74.94 W. This is consistent with the observed CPU
limits; the correct upstream policy change remains to be established.

### Candidate direction for GPU-zone policy

Linux's power allocator treats the first passive trip as its switch-on point
only when a second passive trip exists. With just one it is always active.
The documented two-trip arrangement therefore offers an upstream-compatible
direction: introduce a lower switch-on trip and retain the existing 101 C
target and 118 C critical trip. The existing CPU cooling maps would stay bound
to the target trip. Below the switch-on temperature, the governor explicitly
allows maximum power; the earlier live `step_wise` comparison demonstrates
why removing the cool-temperature restriction matters, but is not a test of
this two-trip candidate.

This is not yet a validated patch: the switch-on temperature changes when
control begins and the default PID gains depend on the distance between the
two trips. The GPU zones also lack an explicit sustainable-power value, so
adding a trip alone does not establish a correct hot-load power budget. Two
trips at exactly 101 C are not a shortcut: the kernel's gain estimation
explicitly gives up for equal-temperature trips. A suitable switch-on point,
power model and behavior under real hot GPU/CPU loads require evidence and
upstream review; the shared J614s/J616s policy must work on both. Do not
replace the current policy or assert that hot protection is qualified based
on the cool-load A/B test.

### Experimental two-trip candidate

[The experimental change](https://github.com/aurora-silicon/linux/pull/852)
adds a passive 100 C switch-on trip before the existing 101 C target in each
of the seven GPU zones. The 100 C value is a provisional choice, not a
measured or qualified threshold; it starts control 1 C before the firmware
limit described in #511. The existing 101 C maps, 5 C target hysteresis and
118 C critical trips remain unchanged. The switch-on trip has no cooling map.
The power allocator compares the actual temperature to its switch-on trip in
its `manage` callback, and below that temperature resets its PID state and
allows maximum power for the target-trip actors. Its switch-on comparison
does not use the new trip's hysteresis.

The candidate is proposed for discussion in draft [Aurora Linux #852](https://github.com/aurora-silicon/linux/pull/852),
based on #795. The submitted tree matches local experimental branch
`codex/j614-j616-gpu-thermal-experiment`; the public commit is
`2bffe0c131924b078cfbe0b460c207f463d80823`. It remains a draft pending review
of the threshold and sustainable power and testing on J616s and near the
actual switch-on temperature.

The owner confirmed that only the J614s is available locally; J616s hardware
testing must come from another tester. Aurora #511's discussion explicitly
left its original J616s GPU benchmark comparison pending; that is not evidence
that the current two-trip proposal has been tested on J616s.

Both J614s and J616s DTBs compiled from #795 with the experimental patch. In
each, the decompiled tree differs from its baseline only by the seven new
trip nodes. A second J614s build uses the currently installed PR-stack source;
its decompiled tree differs from the installed package DTB only in those
seven nodes. A candidate loader was assembled from that DTB and the verified
Aura and U-Boot payloads for the trial.
On 2026-11-02 the candidate was selected for a trial. The previously booted
loader was verified and preserved as `/boot/efi/m1n1/boot.bin.m4rch-before-gpu-thermal`
and under `/var/lib/m4rch/gpu-thermal-before-20261102T081733Z`. The candidate
booted successfully (boot ID `18f0bfc9-9e32-4d9d-8c68-9fa6ac42f514`), and
the verified normal loader was restored for the next boot while the trial
continues running.

At and above 100 C, this changes the controller's PID gain as well as its
activation: with the present estimated 4.62 W sustainable power, the initial
proportional allocation near 100 C can be around 13.86 W before the integral
term, compared with roughly 4.7 W for the one-trip configuration. Both reach
the same feed-forward allocation at 101 C before integral and derivative
effects, while the new configuration responds more sharply above target. These
figures follow from the current kernel's gain estimation, not a hot-load test.
The zero-hysteresis switch-on can also chatter around 100 C. Thus neither
the new threshold nor its hot-load behavior is ready to promote or submit as
a demonstrated fix.

After boot, all seven GPU zones showed the expected 100 C and 101 C passive
trips, 118 C critical trip, and `power_allocator` governor. A 20-second P0
workload completed with the existing guards; GPU temperature peaked at
49.53 C, CPU Die Max at 78.73 C, and TVMR/TVMr at 75.91 C. In 74 load
samples the P0 cooling state remained zero. An isolated trace captured 25
temperature events from each GPU zone and no GPU-attributed CPU power-limit
events; its header reports 1,550 of 1,550 events retained. The preceding
one-trip comparison had nonzero P0 cooling in 70 of 74 samples. P0 average
reported target/actual frequencies were 4.512/4.091 GHz in this trial and
4.074/3.949 GHz in the earlier run; differing conditions make these unsuitable
as a controlled performance claim. Private trace and telemetry are stored as
`gpu-two-trip-after-reboot-trace.txt` and `gpu-two-trip-p0-after-reboot.jsonl`
in the root-only evidence directory. The diagnostic module and trace instance
were removed after capture; the diagnostic module tainted this running kernel.

To exercise the real control path without heating the hardware to 100 C, a
second test temporarily lowered **only gpu0**'s switch-on and target trips
to 52/53 C, keeping the 118 C critical trip and other six zones unchanged.
During a guarded GPU plus P0 workload, P0 state was 0 in all 37 samples below
52 C. After gpu0 rose through 52 C, P0 entered nonzero cooling states (17 of
21 samples; states 2, 8 and 10). After restoring the switch-on trip to 100 C
while the workload continued, P0 state returned to 0 in all 20 samples.
The trace attributed 15 CPU limit events to gpu0, 14 nonzero, and retained
all 1,461 events. A triangle/readback, compute and geometry GPU check passed
before the stress workload was deliberately interrupted after the transition.
The CPU, hottest GPU-zone and TVMR/TVMr peaks were 81.25, 55.82 and 82.04 C.
All seven original trial trip values and governors were checked afterward;
the diagnostic module and trace instance were removed. The temporary trip
controller also had an independent restore watchdog. Private evidence is
`gpu-transition-trial.jsonl`, `gpu-transition-lowered-trip.jsonl`,
`gpu-transition-lowered-trip-gpu.log` and `gpu-transition-trace.txt`.

This demonstrates entry to and release from cooling on the real system, but
release was induced by restoring the threshold, not by observing the GPU cool
through it. It does not validate the chosen 100 C threshold, hot-load thermal
behavior, or the J616s. An appropriate sustainable power and hot-side behavior
need a separately reviewed procedure, given the unqualified TVMR and TVMr
limits observed during prior load tests.

### Sustained GPU qualification attempt

On the same trial boot, a 120-second GPU-only workload completed on battery
power. Native Mesa reported successful rendering and compute readback and
751,129 compute dispatches. Independent guards were set to 90 C CPU, 101.5 C
GPU, and 105 C for TVMR/TVMr, with a separate heartbeat watchdog. There were
441 load samples, with maximum interval 0.284 s. CPU Die Max peaked at
84.89 C, the hottest GPU zone at 65.59 C, and the hotter of TVMR/TVMr at
101.28 C. These guards are experimental limits, not established component
ratings. The workload ended normally and the heartbeat did not fire.

The isolated trace retained 7,627 of 7,627 events, including 123 or 124
temperature updates per GPU zone. No CPU-limit event was attributable to a
GPU zone and P0 cooling was zero in all load samples. This supports sustained
normal-temperature operation, not the behavior at the 100/101 C trips. The
additional readings approached their provisional guard while the GPU remained
over 34 C below switch-on; extending or increasing load without identifying
those sensors and their limits is not a sound way to qualify the hot side.
The diagnostic module and trace instance were removed. No thermal governor,
trip, boot loader or fan setting was changed for this run. Private evidence
uses the `gpu-hot-qualification-120` prefix in the root-only evidence folder.

### Natural cooldown attempt and aggressive above-target response

A subsequent guarded test warmed the GPU for 20 seconds, then temporarily set
GPU0's switch-on/target trips to 47/48 C and ran a 30-second P0 workload while
watching the real GPU0 sensor cool. GPU0 fell from 50.57 to 49.13 C, never
crossing 47 C, so this attempt did not verify release on natural cooldown.
All 146 observations of P0 cooling state were 18, the device's maximum state.
The trace attributed 36 limit events per CPU cluster to GPU0: P0 and P1 at
state 18 and E at state 6. Both workloads completed; their highest CPU, GPU and
TVMR/TVMr readings were 64.03, 52.97 and 78.53 C respectively. All trace
events were retained, the original 100/101 C trips and loader were restored,
and the diagnostic module and trace instance were removed.

This is a materially aggressive response to a real sensor roughly 1–2.6 C
above the **temporarily lowered** target; it is not a measurement made at
101–104 C. The trip spacing was nevertheless the same 1 C as the candidate,
and the result reinforces the need to review PID gains and sustainable power
before considering the candidate ready to merge. Evidence files use the
`gpu-natural-cooldown`, `gpu-cooldown-warmup`, and `gpu-cooldown-p0` prefixes
in the root-only evidence folder.

The kernel's default proportional-gain estimate also explains why: the
above-target gain is sustainable power divided by the trip separation.
With a 1 C separation and no positive integral compensation, the proportional
term removes approximately the entire sustainable-power budget 1 C above the
target. Accumulated negative integral error can reduce it sooner. Thus the
proposal can reach zero allocated CPU power near 102 C even though the earlier
single-trip estimate was much less aggressive there. This is a code-derived
expectation, corroborated at the lowered test temperatures, not a physical
measurement at 102 C. The upstream draft calls out this design tradeoff.

### Five-degree gap comparison

On the same boot, GPU0 was temporarily given a 43 C switch-on and 48 C
target, then the allocator was rebound so it recomputed gains for the 5 C
gap. Its observed sustainable power was 4,620 mW and `k_po/k_pu/k_i` were
946/1,892/189, versus 4,730/9,461/946 with the 1 C gap. A guarded P0
workload completed with GPU0 between 49.07 and 49.56 C, approximately
1.1–1.6 C above the lowered target. Within the common 49.131–49.557 C
temperature range, P0 was at maximum cooling state 18 in 39 of 59 samples;
the earlier 1 C gap test had state 18 in 57 of 57. The wider gap delayed
maximum cooling but did not avoid it. Its full 66 workload samples included
states 0, 11, 13, 14, 15 and 18. The comparison uses separate short runs,
so it is not a controlled performance benchmark or a choice of production
thresholds. CPU/GPU/TVMR-or-TVMr peaked at 77.00/50.20/77.60 C, all trace
events were retained, and trips, governor and original gains were restored.

The DTS parser supports `sustainable-power` and
`integral-time-constant-ms`, but does not load independent proportional gain
values from the thermal-zone DT. Widening the trip gap activates the governor
earlier; changing sustainable power or integral timing without measurement
would also change real cooling behavior. The measured near-target saturation
therefore cannot be resolved by simply selecting an arbitrary wider gap.
Private evidence uses the `gpu-gap-five-degrees` prefix.

The 4,620 mW default was independently reconciled with the running energy
model and `estimate_sustainable_power()`: it sums each bound CPU cooling
device's modeled power at its maximum cooling state. For P0, E and P1 the
minimum-frequency model values are 513, 81 and 561 mW per CPU after conversion
from microwatts; each policy spans four CPUs, giving 2,052 + 324 + 2,244 =
4,620 mW. The corresponding maximum-frequency total is 74,944 mW. This is the
governor's minimum-frequency fallback model, not a measurement of sustainable
CPU power at a 101 C GPU temperature. At the 101 C target the feed-forward
budget is therefore 4.62 W; at a 100 C switch-on the default proportional plus
feed-forward terms initially give approximately 13.86 W, before integral and
derivative terms. Actual cluster limits also depend on requested power and
the cooling devices' load normalization. A credible replacement budget needs
joint CPU/GPU evidence at the control temperature and compatible energy-model
units; the measured all-core CPU-only budget is not such a measurement.

### Trip placement tradeoff

The board-tree comment says the GPU firmware starts limiting at 101 C and
CPU shedding should start at that same temperature. A switch-on at 100 C
begins the GPU-zone allocator one degree earlier than that stated intent.
Changing it to 101/102 C would start at 101 C but moves the allocator target
one degree above the firmware limit; 96/101 C retains the target and softens
the proportional slope but starts five degrees early. Neither alternative has
been boot-tested or justified as a production policy.

The running boot reports T6040 GPU firmware build 25G83. Its G17 driver source
initializes the firmware power-state object with a documented fast-die target
of 101 C and release value of 96 C (`POWER_STATE_WORDS`, offsets 0xc8/0xcc).
The 25G83 initialization path writes those words to that object. This supports
understanding what the installed Linux driver requests, but the constants are
driver-supplied and derived from another implementation; they are not an
independent readout or J614s-specific validation of Apple's firmware limits.
In particular, the firmware's 96 C *release* value is not a reason to assume
that the Linux power allocator should switch on at 96 C: that allocator's
switch-on point starts CPU power allocation above the trip rather than
implementing the firmware limiter's release hysteresis. Neither value defines
a limit for `TVMR` or `TVMr`.
Source: [25G83 power-state words](https://github.com/aurora-silicon/linux/blob/dc054fb02bfb002e41f2dd8f43a3dce2983cf537/drivers/gpu/drm/asahi/g17/fw/initdata/v25g83.rs#L616-L619).

For comparison, with the observed fallback `sustainable-power=4.62 W`,
default gains, zero initial integral/derivative terms and no maximum-power
clamp, the following are *calculated aggregate budgets*, not measured CPU
power or a validated thermal model. Below switch-on the GPU zone permits
maximum power; other zones may still limit CPUs.

| Switch / target | 100 C | 101 C | 102 C | 103 C |
|---|---:|---:|---:|---:|
| 100 / 101 C (draft) | 13.86 W | 4.62 W | ~0 W | 0 W |
| 101 / 102 C | inactive | 13.86 W | 4.62 W | ~0 W |
| 96 / 101 C | 6.47 W | 4.62 W | 3.70 W | 2.77 W |

The negative integral term can lower the budget further as an overshoot
persists. A calculated zero budget maps to the cooling devices' minimum
frequency, not to physically unpowered CPUs. These figures expose the policy
tradeoff; choosing among them still requires credible joint-load and board
evidence, including J616s.

Aurora's J700 and J613 trees provide a useful two-trip precedent rather than
a transferable M4 Pro tuning: both use 58 C switch-on and 95 C control, and
their comments describe measuring their own fanless CPU loads before choosing
the budgets. The J700 comment reports higher gains oscillating under a heavy
load and explains its cooling-map limits and weights. The J613 uses a different
measured budget and reports a combined CPU/GPU observation. These observations
support testing the complete controller and its workload dependence, but do
not establish safe J614s/J616s trip points, power budgets or stability.
Sources: [J700 tree](https://github.com/aurora-silicon/linux/blob/dc054fb02bfb002e41f2dd8f43a3dce2983cf537/arch/arm64/boot/dts/apple/t8140-j700.dts),
[J613 tree](https://github.com/aurora-silicon/linux/blob/dc054fb02bfb002e41f2dd8f43a3dce2983cf537/arch/arm64/boot/dts/apple/t8122-j613.dts).

In particular, with the default proportional gain and a fixed 1 C trip gap,
changing only `sustainable-power` scales both the feed-forward budget and the
above-target proportional gain together. Subject to fixed-point rounding and
integral/derivative terms, their proportional sum therefore still reaches zero
about 1 C above target for any positive budget. A longer
`integral-time-constant-ms` can slow integral accumulation, but it does not
change this proportional zero. These are consequences of the currently
running governor's source, not measured safe operating limits; setting a
different budget alone is not a demonstrated correction for the abrupt
above-target response.

### TVMR / TVMr identity and limits

Aurora exposes both keys as generic SMC temperature channels, without a
component identity or associated `temp*_max`/`temp*_crit` limit. The hardware
metadata inventory identifies each as a readable four-byte `flt` key; metadata
alone does not establish whether the number is a physical measurement, a
derived estimate or a threshold. Other `TVM`-family floats sampled over 326
snapshots (`TVMD`, `TVMx`, `TVmD`, `TVmS`, `TVms`) were constant; their names
and values do not establish a temperature limit.

Third-party sources disagree. [iSMC's sensor table](https://github.com/dkorunic/iSMC/blob/master/smc/sensors.go)
calls TVMR and TVMr virtual memory sensors, whereas
[MacMonitor's M2 sensor reference](https://github.com/ryyansafar/MacMonitor/blob/main/SENSORS.md)
associates TVMr with a memory voltage regulator and places it alongside TMVR.
The latter reference is for a different Mac and does not establish a J614s
rating. On this J614s the keys are clearly distinct: during one prior
all-core observation TVMR/TVMr were 107.29/107.45 C while TMVR was 55.8 C;
during an earlier GPU snapshot they were 90.9/90.2 C while TMVR was 47.9 C.
Values being different do not by themselves prove different physical locations,
but they rule out treating the two keys as interchangeable readings here.

Across the 120-second GPU run TVMR and TVMr tracked closely (Pearson r=0.9985,
median absolute separation 0.82 C, 441 samples). Their correlation also
exceeded 0.998 in the 1,800 MHz all-core run. This supports a relationship
between the reported values; because both workloads warm over time, it does
not identify their source or prove a shared physical sensor. A
[macOS user report](https://github.com/macmade/Hot/issues/125) describes
similar readings up to 108 C on another unspecified Mac, but neither that
anecdote nor a generic VRM rating establishes this Mac's allowable limit.

No J614s-specific maximum or calibrated mapping has been found. The 105 C
experiment cutoff remains a provisional guard, not a discovered safe limit.
Direct comparison with the same Mac under macOS, or J614s firmware/component
documentation, could narrow the interpretation; a macOS observation alone
would still not prove the lifetime or safety limit. The one GPU workload
attempted peaked at 65.59 C while these readings reached 101.28 C, so it also
does not establish how to reach 100 C GPU safely.

A guarded fixed-frequency energy-model sweep was completed. Original
per-policy user frequency-QoS requests are read separately from effective
`scaling_max_freq` and restored after every point; GPU governors are restored
when the sweep exits. Results at frequencies not held by the hardware are not
valid measurements at the requested point. The reduced samples and thermal
ceiling cannot by themselves qualify full-load J614s sustainable budgets.

## Frequency sweep

The fixed-frequency sweep was run on AC power with the GPU-zone governors
temporarily set to `step_wise`, to isolate the CPU energy observations from the
unexpected cool-GPU-zone limits described above. CPU-zone protection remained
active. Each row uses the second half of an eight-second load after a 2.5-second
baseline. P0/P1 readings are total SMC core-rail power with one pinned worker;
other activity on the cluster and idle rail power are included. For E, four
workers are used and the estimate follows #605's `idle + (load - idle) / 4`.
These are short, uncalibrated measurements, not validated replacement values.

| Cluster | Requested MHz | Observed MHz | Rail W | Idle W | Estimated per core W | J616s model W | Status |
|---|---:|---:|---:|---:|---:|---:|---|
| P0 | 1260 | 1260 | 0.829 | 0.030 | 0.829 | 0.513 | held |
| P0 | 1512 | 1512 | 1.083 | 0.147 | 1.083 | 0.715 | held |
| P0 | 1800 | 1800 | 1.288 | 0.274 | 1.288 | 0.907 | held |
| P0 | 2088 | 2088 | 1.550 | 0.113 | 1.550 | 1.158 | held |
| P0 | 2352 | 2352 | 1.945 | 0.426 | 1.945 | 1.494 | held |
| P0 | 2616 | 2616 | 2.342 | 0.449 | 2.342 | 1.783 | held |
| P0 | 2868 | 2868 | 2.847 | 1.179 | 2.847 | 2.210 | held |
| P0 | 3096 | 3096 | 3.277 | 0.654 | 3.277 | 2.637 | held |
| P0 | 3300 | 3300 | 4.583 | 0.811 | 4.583 | 3.247 | held |
| P0 | 3468 | 3468 | 4.265 | 1.032 | 4.265 | 3.669 | held |
| P0 | 3624 | 3624 | 5.059 | 1.109 | 5.059 | 4.128 | held |
| P0 | 3756 | 3756 | 6.240 | 1.338 | 6.240 | 4.819 | held |
| P0 | 3852 | 3852 | 6.412 | 0.878 | 6.412 | 4.978 | held |
| P0 | 3924 | 3924 | 6.975 | 1.266 | 6.975 | 5.316 | held |
| P0 | 3996 | 3986 | 7.239 | 1.612 | 7.239 | 5.576 | held |
| P0 | 4044 | 3991 | 8.702 | 1.626 | 8.702 | 5.773 | clipped/mixed; exclude |
| P0 | 4104 | 3980 | 7.398 | 1.692 | 7.398 | 5.969 | clipped/mixed; exclude |
| E | 1020 | 1020 | 0.210 | 0.020 | 0.067 | 0.082 | held |
| E | 1404 | 1404 | 0.509 | 0.012 | 0.137 | 0.133 | held |
| E | 1788 | 1788 | 0.787 | 0.135 | 0.298 | 0.209 | held |
| E | 2112 | 2112 | 1.170 | 0.024 | 0.311 | 0.301 | held |
| E | 2352 | 2352 | 1.500 | 0.115 | 0.461 | 0.384 | held |
| E | 2532 | 2532 | 1.774 | 0.018 | 0.457 | 0.478 | held |
| E | 2592 | 2592 | 1.927 | 0.008 | 0.488 | 0.531 | held |
| P1 | 1260 | 1260 | 0.850 | 0.055 | 0.850 | 0.562 | held |
| P1 | 1512 | 1512 | 1.166 | 0.048 | 1.166 | 0.772 | held |
| P1 | 1800 | 1800 | 1.475 | 0.076 | 1.475 | 0.989 | held |
| P1 | 2088 | 2088 | 1.796 | 0.045 | 1.796 | 1.302 | held |
| P1 | 2352 | 2352 | 2.275 | 0.055 | 2.275 | 1.644 | held |
| P1 | 2616 | 2616 | 3.098 | 0.043 | 3.098 | 2.004 | held |
| P1 | 2868 | 2868 | 3.123 | 0.261 | 3.123 | 2.349 | held |
| P1 | 3096 | 3096 | 3.419 | 0.182 | 3.419 | 2.723 | held |
| P1 | 3300 | 3300 | 4.114 | 0.428 | 4.114 | 3.333 | held |
| P1 | 3468 | 3468 | 4.520 | 0.460 | 4.520 | 3.712 | held |
| P1 | 3624 | 3624 | 5.056 | 0.537 | 5.056 | 4.130 | held |
| P1 | 3756 | 3756 | 6.137 | 0.588 | 6.137 | 4.666 | held |
| P1 | 3852 | 3846 | 6.366 | 0.566 | 6.366 | 4.881 | held |
| P1 | 3924 | 3852 | 6.204 | 0.806 | 6.204 | 5.177 | clipped/mixed; exclude |
| P1 | 3996 | 3852 | 6.737 | 0.843 | 6.737 | 5.306 | clipped/mixed; exclude |
| P1 | 4044 | 3852 | 6.119 | 2.488 | 6.119 | 5.619 | clipped/mixed; exclude |
| P1 | 4104 | 3852 | 6.360 | 0.660 | 6.360 | 5.843 | clipped/mixed; exclude |

The 4.104 GHz points and several other high-frequency points did not hold
their requested hardware frequencies and must not be used as measurements at
those requested frequencies. Most lower P-cluster raw rail values
were higher than the inherited model in this run; background work and
measurement conditions can contribute. Repeatability and isolated measurement
are needed before changing OPP entries. All user frequency-QoS requests and GPU
governors were read back after restoration.

## All-core measurements

With the GPU-zone governors temporarily on `step_wise` to remove their cool-zone
CPU caps, all twelve cores ran for 120 seconds with both P clusters pinned to
2.088 GHz. The last 30 seconds averaged 84.77 C CPU Die Max, and PR0b, PP0b
and PP2b averaged 4.93, 6.23 and 2.00 W respectively (13.16 W combined). CPU
temperature continued to rise across the run, so this is an operating point,
not an established thermal equilibrium. Both fans started around 110 seconds
at a sampled CPU temperature of 85.3 C; their mode read afterward was automatic
(`F0Md=0`, `F1Md=0`). The monitor and extra diagnostic compilation ran on the
E cluster during the run; the compilation ended before the final 30 seconds.

At 3.096 GHz on both P clusters, the same all-core load hit the 93 C guard after
9.8 seconds, with a 93.02 C peak and fans already running near their minimum.
The last ten samples averaged approximately 11.27 W PR0b, 12.34 W PP0b and
2.01 W PP2b. This is a transient, not a sustainable budget. All original
frequency-QoS requests and seven GPU-zone governors were restored after both
runs. A longer 2.088 GHz run was stopped after approximately 296 seconds when a
separate full-hwmon snapshot showed `TVMR=107.29 C` and `TVMr=107.45 C` while
CPU Die Max was 88.25 C. These two exposed temperature-labelled keys were not
part of the original CPU/GPU-only guard. Their names and values have been
associated with power regulation in [an independent Mac sensor discussion](https://github.com/ryyansafar/MacMonitor/issues/12),
but their precise meaning, calibration and safe limits on J614s are not
established. The readings fell after stopping the workload. Both fans were in
automatic mode and the original QoS requests and governors were restored. The
monitor was then extended to include both keys with a conservative 105 C
stop trigger for any subsequent run. The interrupted run was not a qualified
maximum-budget test.

An independent [MacMonitor report](https://github.com/ryyansafar/MacMonitor/issues/12)
associates `TVMR`/`TVMr` with voltage regulation and reports comparably high
readings on another Mac. This is suggestive, not a specification of this
J614s's sensor calibration or limits. A follow-up 30-second GPU run used the
revised CPU/GPU and `TVMR`/`TVMr` guard; the latter peaked at 93.26/92.48 C,
with the workload and readback passing. Under that GPU load the SMC PR1b and
PS1b readings rose, but their precise rail identity is unconfirmed.

A 600-second all-core observation at 1.512 GHz per P cluster completed,
with the GPU-zone governor temporarily set to `step_wise`, the same CPU/GPU
guard and the additional `TVMR`/`TVMr` guard. CPU QoS requests and GPU
governors were restored. A second SMC metadata-only inventory under the load
produced the same 3,372 records as the first one. Sleep was inhibited only
while measurement and subsequent cooldown observation were active.

In a separate guarded 30-second GPU run, `PR1b` rose from a baseline mean of
0.57 W to 2.83 W and `PS1b` from 0.46 W to 3.89 W. A separate E-core-only
run did not show comparable increases. These are useful candidates for GPU
power correlation, not proven rail identities: desktop activity, the compositor
and other loads were not eliminated. All exposed sensor values are private
snapshots; no firmware or unique device blobs are part of this report.

### Ten-minute all-core observation at 1.512 GHz

Each of the eight P cores was busy at an observed 1.512 GHz and all four E
cores were busy near 2.592 GHz, with AC connected. The monitoring process ran
on E CPU 1. Both fans remained at approximately 2317/2502 RPM in SMC auto
mode, and all sampled PMP fast-die effort lanes stayed at zero.

| Seconds | Samples | CPU °C mean/max | TVMR °C mean/max | TVMr °C mean/max | CPU rails W | Fans RPM | PMP max |
|---:|---:|---:|---:|---:|---:|---|---|
| 0–60 | 224 | 71.9/74.3 | 85.9/88.9 | 86.6/89.8 | 8.56 | 2316/2501 | 0/0/0 |
| 60–120 | 224 | 75.2/76.1 | 90.4/91.8 | 91.2/92.7 | 8.76 | 2316/2502 | 0/0/0 |
| 120–180 | 224 | 76.5/76.8 | 92.5/93.6 | 93.5/94.7 | 8.80 | 2317/2502 | 0/0/0 |
| 180–240 | 223 | 77.1/77.5 | 93.7/94.3 | 94.7/95.4 | 8.81 | 2317/2502 | 0/0/0 |
| 240–300 | 224 | 77.5/78.0 | 94.5/95.1 | 95.3/95.8 | 8.81 | 2316/2501 | 0/0/0 |
| 300–360 | 223 | 77.8/78.2 | 95.1/95.6 | 95.8/96.2 | 8.84 | 2316/2502 | 0/0/0 |
| 360–420 | 223 | 78.2/78.4 | 95.5/96.0 | 96.2/96.5 | 8.83 | 2316/2501 | 0/0/0 |
| 420–480 | 224 | 78.5/78.9 | 95.8/96.2 | 96.5/96.8 | 8.83 | 2317/2502 | 0/0/0 |
| 480–540 | 223 | 78.7/79.1 | 96.0/96.5 | 96.8/97.2 | 8.87 | 2317/2502 | 0/0/0 |
| 540–600 | 224 | 78.8/79.1 | 96.2/96.6 | 97.0/97.4 | 8.83 | 2317/2502 | 0/0/0 |

Outcome: completed

This provides one sustained operating point, not the maximum sustainable
CPU budget: the workload is capped at 1.512 GHz on P cores, and the readings
were still increasing slightly near the end. It does not qualify the 51.3 W
J616s total budget or determine the J614s temperature limits. The five-minute
cooldown observation is recorded separately.

During the final minute of the 1.512 GHz run, mean rail readings were 3.130 W
PR0b, 3.773 W PP0b and 1.926 W PP2b. Total-system power averaged 25.855 W and
heatpipe power 16.430 W; those are distinct SMC channels and must not be added
to the CPU rails as if they were independent measurements. The final two-minute
linear slopes were approximately +0.06 C/min for CPU Die Max, +0.21 C/min for
`TVMR`, and +0.30 C/min for `TVMr`; the latter two were not fully flat.

During the passive cooldown after that run, fan modes read `F0Md=0` and
`F1Md=0` (automatic) while both fans ran near 2317/2502 RPM. They remained on
for almost five minutes after the workload stopped. In the sample at 300
seconds, both read 0 RPM and both modes read 3 (firmware system mode), with CPU
Die Max 59.23 C and the hotter of `TVMR`/`TVMr` 72.10 C. No fan keys were
written by these experiments. This is a single observed transition; the data
do not establish a complete fan curve or its trigger.

Four representative P-cluster points were repeated after cooldown, now also
recording rail voltage and `/proc/stat` CPU utilization. At 2.088/3.096 GHz,
P0 measured 1.597/3.289 W versus 1.550/3.277 W in the first sweep; P1 measured
1.779/3.465 W versus 1.796/3.419 W. The targeted core was 100% busy and its
three sibling CPUs were approximately 0.5–2.6% busy in these windows. These
repeats strengthen the observation that the J614s rail readings differ from
the J616s-derived table, without establishing a production energy model.
The remaining 27 preselected OPPs were measured with the additional
`TVMR`/`TVMr` guard. Across the 41 initial and follow-up frequency points,
six did not hold the requested frequency within 1% on average and are marked
clipped/mixed in the table. Repeated endpoints also captured voltage and
per-core utilization. All 49 point runs, including repeats, completed.

A preliminary fit of measured raw P-cluster rail power against `V² × GHz`,
following the form used in #605, gave P0 `k=1.889`, `c=-0.094 W`, RMS
`0.166 W` across 14 eligible points and P1 `k=1.701`, `c=0.038 W`, RMS
`0.126 W` across 12. This fit excludes points whose individual hardware
frequency samples departed by more than 1%, whose target worker was below
90% busy or whose sibling cores exceeded 15% busy. For comparison, #605
reported J616s fits `k=1.458` and `1.396`. A single machine, the uncalibrated
SMC sensors, short windows, background power and clipped top states limit the
comparison. The fit is not a replacement OPP table or a sustainable-power
budget. Full fit output remains in the private working cache.

## Remaining work

- The GPU-zone allocator behavior is reproducible and source-explained; an
  upstream-compatible correction still needs design and hardware validation.
  The comparison temporarily changed governors, but the installed policy was
  restored and no fix was applied.
- High-load steady-state thermal limits and a production J614s sustainable
  budget remain unknown. The provisional 93 C CPU/GPU and 105 C `TVMR`/`TVMr`
  stop thresholds were experiment guards, not validated component limits.
  The first high reading was discovered only through an independent snapshot;
  it fell after stopping. Establishing the sensor meanings and acceptable
  procedure requires further evidence and supervision; a reboot alone would
  not establish them.
- The temporary diagnostic module and all test sleep inhibitors were removed.
  Loading an out-of-tree module taints this kernel for the remainder of this
  boot. The normal package-managed GRUB entry is the one that actually booted.

A guarded 1.800 GHz all-core midpoint measurement completed to narrow the
range between the completed 1.512 GHz point and the interrupted 2.088 GHz run.

The E-cluster estimate is not monotonic in the short sweep (for example,
0.461 W at 2.352 GHz versus 0.457 W at 2.532 GHz per the J616s method).
Baseline activity and sensor noise therefore matter; these observations should
not be pasted into a replacement OPP table without repeat measurements and an
appropriate model.

The J614s fan hwmon endpoints report a minimum of 2317 RPM and maximum of
7826 RPM for each fan. The shared J616s comment gives different figures
(1350/5777 RPM); the hardware-reported values should not be replaced by those
comment values. The inherited final DT removes the old host fan cooling maps,
so the ladder figures in that earlier comment do not describe an active
Linux-controlled fan ladder on this boot.

During the 1.800 GHz all-core observation, a full snapshot read all 475 exposed
SMC hwmon channels without errors. The hottest reported channels in that
snapshot were the two additionally guarded keys `TVMr` (99.5 C) and `TVMR`
(98.6 C); their precise identities and limits remain unverified.

An independent heartbeat watcher was added during the later 1.800 GHz run:
if the guard stops updating its trace for more than five seconds, it kills the
guard's owned workload process groups. This supplements the guard's
parent-death signals and finite workload deadlines; it does not establish a
hardware temperature limit.

### Ten-minute all-core midpoint at 1.800 GHz

The 1.800 GHz run completed 599.9 seconds. In the final minute, PR0b, PP0b
and PP2b averaged 4.037, 4.966 and 2.030 W (11.03 W combined); total-system
power averaged 29.106 W and heatpipe power 19.160 W. Hardware-reported mean
P0/E/P1 frequencies were 1.800/2.592/1.800 GHz. The CPU Die Max, `TVMR` and
`TVMr` peaks were 83.64, 103.07 and 103.49 C. PMP fast-die effort was zero
in all sampled lanes. The maximum sample interval was 0.31 seconds; the
independent heartbeat watchdog did not trigger. Both original CPU QoS requests
and all GPU-zone governors were restored and checked.

| Seconds | Samples | CPU °C mean/max | TVMR °C mean/max | TVMr °C mean/max | CPU rails W | Fans RPM | PMP max |
|---:|---:|---:|---:|---:|---:|---|---|
| 0–60 | 225 | 72.1/76.1 | 84.3/90.6 | 84.9/91.2 | 10.54 | 0/0 | 0/0/0 |
| 60–120 | 225 | 78.8/80.2 | 94.5/97.1 | 95.3/97.8 | 10.81 | 627/675 | 0/0/0 |
| 120–180 | 224 | 79.9/80.2 | 97.1/97.7 | 97.9/98.5 | 10.84 | 2317/2502 | 0/0/0 |
| 180–240 | 225 | 80.4/80.9 | 98.1/98.9 | 98.9/99.8 | 10.92 | 2317/2501 | 0/0/0 |
| 240–300 | 225 | 81.2/81.6 | 99.2/99.9 | 99.9/100.5 | 10.91 | 2317/2502 | 0/0/0 |
| 300–360 | 225 | 81.7/82.0 | 100.2/100.9 | 100.8/101.5 | 10.94 | 2317/2502 | 0/0/0 |
| 360–420 | 225 | 82.0/82.3 | 101.0/101.6 | 101.5/102.2 | 10.93 | 2317/2502 | 0/0/0 |
| 420–480 | 224 | 82.3/82.6 | 101.7/102.1 | 102.2/102.7 | 10.99 | 2317/2502 | 0/0/0 |
| 480–540 | 225 | 82.7/83.0 | 102.2/103.0 | 102.7/103.2 | 11.01 | 2317/2501 | 0/0/0 |
| 540–600 | 225 | 83.1/83.6 | 102.7/103.1 | 103.1/103.5 | 11.03 | 2316/2502 | 0/0/0 |

Outcome: completed


Over the final two minutes, CPU, `TVMR` and `TVMr` rose at approximately
0.35, 0.50 and 0.44 C/min respectively. Thus the run did not reach a clearly
flat equilibrium and does not qualify a maximum thermal budget. The provisional
105 C extra-sensor guard and the unqualified identity and limit of those keys
remain material constraints.

After the 1.800 GHz workload stopped, the two additional readings fell from
approximately 96 C to 93 C over the following ten seconds, and CPU Die Max
fell from about 88.5 C to 72 C. Firmware remained responsible for the fans.
The private evidence files were SHA-256 checked after collection; their
manifest is in the same root-only evidence directory.

A final check requested the 4.416 GHz P0 state. After 2.74 seconds of load,
CPU Die Max reached 93.73 C and the 93 C guard stopped the workload. The
hardware-reported frequency ranged from 3.996 to 4.416 GHz, so the result is
not a stable 4.416 GHz power measurement. CPU QoS and GPU-zone policies were
restored. The remaining top states were not attempted after the guard fired.
Higher-load testing and final sustainable budgets require a reviewed procedure
and J614s-specific limits; they do not necessarily require a reboot.
