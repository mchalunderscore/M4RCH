# m4rch native work

Continue on J614s / T6040. Return your own `HANDOVER.md` and raw evidence in a
new `/boot/m4rch-return-*.tar.gz`; preserve this incoming report.

## Established baseline

The previous return confirms right-port YubiKey USB2 in both orientations,
reconnects, SanDisk storage at 480 Mbit/s and a checked 16 MiB file write.
Left-front has no enumeration or power indication with disabled nodes;
left-rear data remains untested while it supplies AC. HDMI had no signal and
no DRM connector; the connected simple framebuffer is the internal display.
Wayland/QPainter compositing and Alice-readable `/boot` are verified. Package
migration has not occurred: the old linux-t6040/arch-m4-config kernel is running.

Both short P-core tests sampled 3.924 GHz while requesting 4.512 GHz. E reached
2.592 GHz. The 1.52 P/E SHA256 throughput ratio is crypto-specific, not a
scheduler capacity ratio. Active-desktop NOP-idle CPU sensors read about
80–87 C; automatic fan targets/RPM rose to roughly 2300/2500. No calibrated
T6040 thermal ceiling or proven throttling cause follows from those readings.

## Source packet

`/boot/source-review-415c9a4a052f.tar.gz` supplies the missing source context.
Extract as Alice into a new directory under HOME, not over a source checkout:

```sh
review="$HOME/m4rch-review-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -m 700 "$review"
tar -xzf /boot/source-review-415c9a4a052f.tar.gz -C "$review"
(cd "$review" && sha256sum -c SHA256SUMS)
```

`project/` supplies build recipes, locks, local patches and provenance;
`wallace/` supplies pinned patches, DTS and harness. `linux-base/` is selected
original source. `usb-result/` reconstructs final USB/PHY/SPMI sources and
matches all five recorded final hashes. `cpu-result/` applies the pinned
Wallace overflow correction. Read the packet README and manifest: this is
selected-file reconstruction, not a complete copy of the running dirty kernel.
Do not apply every Wallace patch or install anything from this packet blindly.

## Clock decoding and placement

Audit `cpu-result/drivers/cpufreq/apple-soc-cpufreq.c` against
`wallace/dts/t6040-cpufreq.dtsi` and the new live DT capture. The T8112-compatible
path reads a five-bit current pstate at status offset 0x50 and maps it through
OPP levels. Verify the T6040 status layout and level table before interpreting
3.924 GHz as thermal limiting. Generic fallback reads the command register;
identify the actual matched compatible. Review target limits, boost handling,
frequency invariance and energy-model/capacity use separately. Return source
locations and a concrete explanation or the exact unresolved evidence.

Run from Alice's terminal, substituting the actual incoming kit ID:

```sh
kit=/boot/cpu-tools-ID
capture="$HOME/m4rch-native-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -m 700 "$capture"
sudo sh "$kit/collect.sh" snapshot --label baseline --output "$capture/baseline"
sudo sh "$kit/run.sh" --cpus all --interval 0.25 --output "$capture/idle" -- sleep 60
```

The collector now includes performance-domains, cpufreq nodes and OPP tables.
Record AC state and background load; compare the desktop with an owner-approved
quiet console interval if convenient. Keep governors, fan ownership and limits.
Use bounded, local workloads only after clock/sensor interpretation. Prefer
compiled scalar/FP and memory tests over Python interpreter or crypto alone;
record compiler/options, working set, affinity and identical start conditions.
Repeat P/E in reversed order and use 0.25-second sampling. Do not force a
capacity ratio or increase sustained loads while cooling remains unresolved.

## Left USB2 source work

The source gap is resolved. Audit `usb-result/drivers/phy/apple/t6040-usb2.c`,
DWC3 cable lifecycle, TIPD and SPMI alongside `project/lib/hardware_profile.py`,
its overlay, and pinned Wallace DTS. The kit's `macos-port-map.json` contains
ADT resource metadata; Linux DT cells are big-endian, ADT bytes little-endian.

Map distinct PHY banks, DART/stream IDs, power domains and connector endpoints
for each left controller. Establish whether the right-port sequence is generic
or contains port-specific assumptions. Preserve AC and the working right port.
Return a reviewed candidate patch with prerequisites and rollback, or a precise
list of remaining facts to collect. Do not enable nodes or poke registers merely
to discover their meaning. Left-rear USB tests can wait until AC can remain on
MagSafe or the owner explicitly chooses a brief battery test.

## Idle and HDMI

Keep `idle=nop arm64.nowfxt`. The previous audit found no live PSCI/cpuidle
states and spin-table CPUs without hotplug shutdown support. T6040 is excluded
from the pinned Apple idle driver; adding its compatible alone is insufficient.
Audit full state preservation and early parking before proposing a candidate.
PSCI-via-EFI requires coordinated resident m1n1/kernel work and enrollment;
EFI presence alone proves neither implementation nor compatibility.

HDMI is recorded as unsupported in this running build. Do not spend another
round changing KScreen/session settings without a native display-controller
and connector path. No new HDMI action is required here.

## Return

Snapshots are root-owned/private. Include versions, source hashes, DT/driver
findings, exact executed tests, patches and rollback; distinguish proposals
from hardware results. No need to repeat the completed orientation/file tests.

```sh
# Write your findings to "$capture/HANDOVER.md" first.
stamp=$(date -u +%Y%m%dT%H%M%SZ)
sudo sh "$kit/collect.sh" bundle --input "$capture" --output "/boot/m4rch-return-$stamp.tar.gz"
sync
```

The previous agent restored a kit file from `FSCK0000.000` with an exact hash
match. Preserve recovery files and report any new recurrence; no filesystem
repair is requested. Keep the incoming kit and captures until the return is
reviewed. Routine SD updates do not require changing the enrolled loader.
