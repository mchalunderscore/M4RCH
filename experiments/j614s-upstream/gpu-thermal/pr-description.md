## Problem

The J614s/J616s GPU zones each have one passive trip at 101°C. With only one
passive trip, `power_allocator` treats it as the target and runs continuously.
On a J614s, a trace showed GPU-zone CPU cooling while GPU sensors were around
57–64°C, contrary to the intended GPU-limit backstop described in #511.

## Proposal

Add a separate 100°C switch-on passive trip before each existing 101°C target.
The existing target cooling maps and 118°C critical trips are unchanged.
The 100°C choice is **provisional**: it starts the controller 1°C before the
GPU firmware limit, but it and the estimated sustainable power need review.
The controller's PID gains change with the separation between the trips. With
the default estimated proportional gain and a 1°C gap, the proportional term
alone reduces the sustainable-power budget to approximately zero at 1°C
above the target; accumulated negative integral error can reduce it sooner.
This may result in maximum CPU cooling near 102°C, and needs review before
the threshold or controller tuning is accepted.

The running J614s estimates sustainable power as 4,620 mW: the CPU cooling
devices' minimum-frequency energy-model powers, summed over the three CPU
policies. It is not a measurement with the GPU held at 101°C. At the proposed
100°C switch-on the default feed-forward and proportional terms initially
allow about 13.86 W combined, falling toward 4.62 W at the target before
integral effects. The actual per-cluster result also depends on demand and
load normalization; a replacement budget needs joint CPU/GPU evidence.
Changing the budget alone scales the default proportional gain with it, so
with the same 1°C gap the proportional budget still approaches zero 1°C above
target; a longer integral time constant does not change that proportional zero.
Aurora's fanless [J700](https://github.com/aurora-silicon/linux/blob/dc054fb02bfb002e41f2dd8f43a3dce2983cf537/arch/arm64/boot/dts/apple/t8140-j700.dts)
and [J613](https://github.com/aurora-silicon/linux/blob/dc054fb02bfb002e41f2dd8f43a3dce2983cf537/arch/arm64/boot/dts/apple/t8122-j613.dts)
use two trips with board-measured budgets and a 37°C gap; J700's source notes
oscillation with higher gains. Those results are useful precedent for
measurement, but their values are not a J614s/J616s tune.

The board-tree comment describes shedding CPU power from 101°C. This draft
would start at 100°C. A 101/102°C switch/target pair would match that onset
but move the governor target above the firmware's 101°C limit; a wider gap
below 101°C would start shedding earlier. Neither alternative has been
qualified. Maintainer guidance on the intended onset and target would help
choose between these tradeoffs.

On the tested J614s, the running driver reports 25G83 firmware. The
[25G83 initialization code](https://github.com/aurora-silicon/linux/blob/dc054fb02bfb002e41f2dd8f43a3dce2983cf537/drivers/gpu/drm/asahi/g17/fw/initdata/v25g83.rs#L616-L619)
writes a documented 101°C fast-die target and 96°C release. These are
driver-supplied constants, not an independent J614s firmware-limit measurement;
the firmware release value is not equivalent to IPA's switch-on temperature.

This is based on #795, whose shared device tree covers both machines. Please
do not merge on the basis of the tests below alone.

## Testing on J614s

- Both J614s and J616s device trees compile; their compiled differences contain
  only the seven new trip nodes. The J614s candidate booted with both passive
  trips and the original critical trip on each GPU zone.
- With GPU zones below 50°C, a 20-second P-core workload had zero P0 cooling
  in 74 samples; a complete trace showed no GPU-attributed CPU limit events.
  The earlier one-trip comparison had nonzero P0 cooling in 70 of 74 samples.
- With only GPU0's trips temporarily lowered to 52/53°C, a guarded real GPU
  and P-core workload crossed the switch-on temperature. P0 cooling was zero
  below it and entered nonzero states above it; after restoring the original
  trips during the workload it returned to zero. GPU rendering and compute
  readback checks passed. Peak CPU/GPU/TVMR-or-TVMr readings were
  81.25/55.82/82.04°C. All trip values were restored afterward.
- A separate 120-second GPU workload passed rendering and compute readback
  with no GPU-attributed CPU limit events. The hottest GPU zone reached
  65.59°C; the hotter of TVMR/TVMr reached 101.28°C. This did not exercise
  the actual 100°C switch-on point.
- In a follow-up with GPU0 temporarily set to 47/48°C, its real sensor stayed
  1.1–2.6°C above the target during a P-core workload. GPU0 requested the
  maximum cooling state on both P-clusters (18/18) and E-cluster (6/6). The
  sensor did not cool through the switch-on trip during the test. This is a
  lowered-trip controller test, not a measurement at 101–104°C, but warrants
  particular review of the candidate's above-target aggressiveness.
- A 43/48°C test recomputed the allocator gains for a 5°C gap, keeping the
  same lowered target. At overlapping GPU temperatures of 49.131–49.557°C,
  P0 reached maximum cooling in 39/59 workload samples, versus 57/57 in the
  earlier 1°C-gap run. The wider gap delayed maximum cooling but did not
  eliminate it; these separate short runs do not qualify a production setting.
  The original trips, governor and gains were restored.

## Still needed

- Review and justify the switch-on point and sustainable-power behavior,
  including the sharper PID response and potential switching around 100°C.
- Validate real behavior near 100°C with a suitable thermal test procedure;
  the lowered-trip experiment does not establish hardware temperature limits.
- Test the change on J616s. The J614s test does not establish its thermal
  response or performance.
