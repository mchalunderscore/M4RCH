# J614s feature status

Snapshot: 31 October 2026. This follows the feature groups in Aurora's
[MacBook Pro 14-inch M4 Pro (J614s) report](https://aurorasilicon.org/devices/?device=j614s),
but records the evidence and remaining work for this machine. Aurora's report
lists basic boot as working, internal display as partial, and the other rows
below as not recorded. Local results do not automatically update that report.

## Status key

- **Ready to PR**: a specific, reviewable contribution is prepared, its
  provenance and eligibility are checked, and device, revision, reproduction
  steps, results and limitations are documented. This is not a promise of
  acceptance.
- **Functional, needs more work**: some relevant behavior has been observed,
  but a complete, appropriately evidenced contribution is not ready. The
  notes identify the missing work; this does not imply every aspect works.
- **Partial**: only part of the feature is known to work.
- **Not working**: the feature is known to be unavailable or disabled.
- **Not recorded**: the available evidence does not establish its behavior.
  This does not mean it is broken.

No row is currently marked Ready to PR: the available records do not establish
that an individual submission and its provenance have been fully reviewed.
Check [Aurora's policies](https://aurorasilicon.org/docs/policies/) and
[contributor guide](https://aurorasilicon.org/docs/contributing/) at submission
time. In particular, contributors must have the right to share their material,
clearly disclose generative AI involvement in the associated commit, document
the exact device, software revision, steps, logs and limitations, and keep
Aurora-derived work within Aurora-controlled spaces. Repository-specific
instructions and templates also apply.

The package versions and scope of the older confirmed normal boot are in
[current system status](docs/status.md). The newer kernel and U-Boot source
records report a successful GRUB keyboard and Linux input handoff trial; they
do not establish that all peripherals were qualified on that build. Where
those records and the older status document differ, the trial is identified
explicitly below.

## Platform

| Feature | Status | Evidence and remaining work |
| --- | --- | --- |
| Boot | Functional, needs more work | The owner reported a normal package-managed boot on the earlier stack. The newer [kernel](packages/linux-m4rch/promoted-source/source-stack.md) and [U-Boot](packages/u-boot-m4rch/promoted-source/source-stack.md) records describe a successful input handoff trial. Resolve the documented source/DTB reconstruction limits, verify the intended final boot stack, and prepare a scoped patch series and reproducible hardware report. A PMP parent-domain failure remains in the earlier boot log. |
| All CPU cores | Functional, needs more work | The owner observed work on all cores in btop and Geekbench scores within roughly 10–15% of macOS. Record the exact configuration, benchmark runs and results for a submission. |
| Internal storage | Functional, needs more work | The normal installed system booted from internal storage; record the exact storage configuration and test evidence for a submission. |

## Display and input

| Feature | Status | Evidence and remaining work |
| --- | --- | --- |
| Internal display | Partial | Aurora records basic display output. Current-stack refresh rate, brightness and broader display behavior need separate qualification. |
| External display | Functional, needs more work | HDMI and USB-C display trials produced a picture. The owner confirmed that the observed HDMI flicker and scaling issues were KWin issues. Record the display modes, software revisions and results for a submission. |
| ProMotion | Functional, needs more work | The owner reports the internal display currently runs at 120 Hz. Adaptive refresh behavior is not established; record the mode and test results for a submission. |
| Brightness control | Functional, needs more work | The owner reports that brightness adjustment works. Record the tested range, software revision and steps for a submission. |
| Keyboard | Functional, needs more work | The owner confirmed GRUB and Linux keyboard input in the handoff trial. Package a reviewable cross-project change and document repeat boots, failure paths and sleep behavior. See the [U-Boot source record](packages/u-boot-m4rch/promoted-source/source-stack.md). |
| Keyboard backlight | Functional, needs more work | The owner reports responsive, reliable adjustment and persistence across reboot. Record the software revision and test steps for a submission. |
| Trackpad | Functional, needs more work | The owner confirmed Linux input after the handoff trial. Test repeat boots and sleep, and document firmware and handoff requirements. |
| Touch ID | Not recorded | No J614s test is recorded. |

## Media

| Feature | Status | Evidence and remaining work |
| --- | --- | --- |
| Speakers | Not working | Internal amplifiers remain disabled pending device-specific protection evidence. See the [speaker safety assessment](docs/j614s-speaker-safety-investigation.md) for the mapping, model and interlock work required. |
| Microphone | Functional, needs more work | The owner reported operation on an earlier build. Retest capture on the intended stack and record formats, steps and results. |
| Camera | Functional, needs more work | The owner reported operation on an earlier build. Retest on the intended stack and record mode and results. |
| Headset jack | Not recorded | A card being present does not establish playback or headset microphone operation. |

## Connectivity

| Feature | Status | Evidence and remaining work |
| --- | --- | --- |
| USB-C | Functional, needs more work | The owner tested all three ports in all three orientations at USB 3 speeds. Record the devices, software revision, test steps and results for a submission. |
| Thunderbolt / USB4 | Not recorded | No J614s test is recorded. |
| HDMI | Functional, needs more work | Display output works; the owner confirmed that the earlier flicker and scaling issues were KWin issues. Record the display mode, software revisions and results for a submission. |
| SDXC card slot | Not recorded | No distinct test is recorded. |
| Wi-Fi | Functional, needs more work | The owner reports using Wi-Fi for this session. Record the adapter, software revision and connection test for a submission. |
| Bluetooth | Functional, needs more work | The owner regularly uses a Bluetooth headset. Record the headset, software revision and pairing and audio results for a submission. |

## Power

| Feature | Status | Evidence and remaining work |
| --- | --- | --- |
| Battery / charging | Functional, needs more work | The owner regularly uses the machine on battery and charges it in Linux. Record the software revision and battery and charging observations for a submission. |
| Fan control | Functional, needs more work | The local service controls both fans, but sustained load and wake are not qualified on the current kernel. Validate the policy and failure behavior on hardware before proposing it. |
| Sleep / resume | Functional, needs more work | Earlier lid trials passed on AC and battery; they predate the current stack. Retest wake, input and peripherals, and document the local sleep override and recovery limitations. |

## Graphics

| Feature | Status | Evidence and remaining work |
| --- | --- | --- |
| GPU acceleration | Functional, needs more work | Native Mesa enumerated the M4 Pro GPU and OpenGL reported Zink on it. Qualify longer workloads and the intended final stack; preserve exact revisions and logs. |
| Vulkan | Functional, needs more work | A short Vulkan rendering run passed on Mesa `c208afc`. Longer workloads and the newer boot stack remain unqualified. |
| Ray tracing | Not recorded | No J614s test is recorded. |
| Video decoding | Not recorded | No J614s hardware decoding test is recorded. |
