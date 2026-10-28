# Internal-panel HDR investigation

Status: HDR is working on the J614s internal panel with the main kernel. The
owner reports that it looks great; the output remains approximate and has not
been calibrated. The investigation and earlier test states are recorded below.

## Upstream findings

- Aurora's package baseline is Linux
  [`9cbdd073`](https://github.com/aurora-silicon/linux/tree/9cbdd0734d9e186c5f5f5949a21b909d10c2571b).
  Searches of Aurora's PRs and commits for HDR did not find an internal-panel
  HDR implementation. Search results are not proof that no private or
  unindexed work exists.
- Asahi's closed, unmerged [PR 431](https://github.com/AsahiLinux/linux/pull/431)
  demonstrated experimental HDR on an M1 Pro with KDE and GNOME. It exposes
  connector colorspace and HDR metadata, substitutes another display's EDID,
  switches the DCP surface format/transfer function, and forces an experimental
  high backlight value. The author says most of it went into a `dcp/scanout`
  branch; we have not located a current accessible version of that branch.
  The demo is neither an M4 Pro result nor a production-ready patch.
- Asahi's [6.19 progress report](https://asahilinux.org/2026/02/progress-report-6-19/)
  describes HDR as early work and explains the plane refactoring. Its
  [7.2 report](https://asahilinux.org/2026/08/progress-report-7-2/) describes
  Interchange and direct scanout progress; direct scanout is a separate
  optimization, not established as a prerequisite for composited HDR.
- Aurora's [PR 451](https://github.com/aurora-silicon/linux/pull/451) concerns
  J616s external displays and VRR, not a qualified internal HDR solution.

## Current boundary

The connected `card1-eDP-1` reports an empty EDID through sysfs. The pinned
Aurora [plane code](https://github.com/aurora-silicon/linux/blob/9cbdd0734d9e186c5f5f5949a21b909d10c2571b/drivers/gpu/drm/apple/plane.c)
contains 10-bit RGB formats but tags RGB surfaces with the SDR transfer
function and native colorspace, including 10-bit framebuffers.

The J614s uses the desktop-26.6 DCP firmware path. The separate T8132 M4
backend's 8-bit-only restriction must not be assumed to apply to this machine.
Current packages pin Mesa `f2c9dc3f`; KWin is 6.8.1.

## Live baseline

Read-only DRM ioctls and `kscreen-doctor -o` on 27 October show:

- Internal eDP-1 is connected and active at 3024×1964, 120 Hz, scale 2.
  Plasma reports HDR and wide color gamut incapable, sRGB profile, no ICC
  profile, and brightness 35%. The backlight interface reads 211 / 600.
- The connector exposes `EDID=0` and `vrr_capable=0`; it has no `Colorspace`
  or `HDR_OUTPUT_METADATA` property. The CRTC exposes CTM and a 257-entry gamma
  LUT property. Presence does not establish HDR processing.
- The primary plane advertises XR30, AR30, AB4H, 8-bit RGB and several YUV
  formats. Its active linear framebuffer is AR30 (10-bit per RGB channel).
  This establishes 10-bit KMS scanout, not HDR, color precision, or luminance.
  An overlay plane exists but was inactive at the snapshot.
- The sandbox did not expose `/dev/dri`; the baseline used an approved
  read-only host invocation. `modetest` did not open this platform device by
  driver name, so a small libdrm program opened card1 and enumerated properties.

## Installed-source audit

`linux-m4rch 7.3.0-4` installs its config and a 107 KiB `kernel.patch` under
`/usr/share/doc/linux-m4rch/`. The patch SHA-256 is
`3a29c298131e8788c0262b2cfd35d2f5b2342c4e13b9624be38f201de4b4df28`.
The package guide identifies Aurora `9cbdd073` as the source baseline. The
six relevant Apple DRM patch sections applied cleanly to the corresponding
files fetched at that commit; this reconstructs those source files, but does
not independently prove the running module was built from exactly that tree.
The installed module-tree and `/boot` kernel images have matching SHA-256
`b28fc15b180e776e09ded58812b85f5c24ec407e8539bc23464a90ce751c446c`.

- `apple_drv.c` gives the desktop path the general plane formats and creates
  its connector without HDR metadata or colorspace properties. The live KMS
  observation agrees.
- `plane.c` maps AR30 to DCP's L10R format; RGB surfaces are tagged SDR and
  native colorspace. `iomfb_template.c` copies that plane surface into the
  desktop-26.6 swap, so a 10-bit desktop alone does not select HDR.
- The parser prefers an SDR RGB/444 color mode when available. A real HDR path
  must investigate mode selection and firmware-advertised EOTFs as well as
  surface tags; the active hardware output mode was not independently captured.
- Desktop-26.6 brightness swaps use a binary64 **nits** value, not the old
  prototype's raw DAC field. The fallback SDR maximum is 600 nits and the live
  backlight maximum is 600. The legacy experiment's forced raw value is not
  applicable to this interface without a separately qualified contract.
- The package patch adds J614s device matching and validation, desktop callback
  validation and boot-mode handling. No HDR-specific change was identified in
  the inspected display patch sections. Other subsystems and full build
  provenance were outside this focused audit.

## Firmware color records on the current boot

The connector's debugfs files retain the firmware's chunked `ColorElements`
and `TimingElements` dictionaries. These are the received property bytes,
copied to the connector by the desktop-26.6 driver, rather than only the
driver's selected mode. A read-only capture and offline decoder using the
tag layout in Aurora's `parser.c` found:

| Firmware field | Advertised value |
| --- | --- |
| Color elements | One, ID 1; not virtual |
| Depth / pixel encoding | 8 / RGB (0) |
| Dynamic range | Full (0) |
| EOTF | SDR gamma (0) |
| Colorimetry | Default RGB (16) |
| Timing entries | Six, IDs 2–7: 120, 60, 48, 59.94, 47.95 and 50 Hz |
| Color modes for each timing | The same ID 1 only |

The decoder consumed each serialized object with one trailing zero byte: the
345-byte color record has SHA-256
`febb28a0b1043b9a45d82153a88c2099fff97b10538963bfab1c0e46c41d2065`,
and the 9513-byte timing record has SHA-256
`5254ec537ee476d1de8841e064a07820ce091c38ba01f8d2f259a5ab6e7b78a7`.
The running boot log records color ID 1, timing ID 2 and 3024×1964 at 120 Hz.
The advertised 8-bit output color mode is a separate concept from the 10-bit
AR30 framebuffer provided to DCP; it does not prove the physical panel's
effective precision.

The driver's enum identifies EOTF 2 as PQ and colorimetry 9 as BT.2020 RGB;
neither appears in these cached output-mode records. The DCP surface ABI has
separate HDR transfer-function and BT.2020 colorspace values. Those surface
tags are distinct from the output-mode enums, and their operation on the J614s
has not been tested. The list therefore shows what this boot advertised, not
what firmware or panel can never do after a different configuration.

Apple specifies this model's panel as P3/XDR with HDR brightness up to 1000
nits sustained full screen and 1600 nits peak, under its stated conditions:
[Apple technical specifications](https://support.apple.com/en-gb/121553).
That is a hardware specification, not evidence that this Linux DCP path
currently exposes those capabilities or a safe value to request directly.
The journal also reports `unusable firmware gamma table, GAMMA_LUT ignored`;
the advertised LUT property should not be assumed to function on this boot.

The current kernel disables ftrace and kprobes, so the existing tracepoints
cannot be enabled on this boot. The retained property bytes nevertheless
avoid needing a reboot just to see this mode catalog. Further progress needs
to establish the firmware's input-surface transfer and brightness behavior,
not merely add an advertised PQ output mode to userspace.

## Work required

1. Trace 26.6 desktop swap construction, mode selection, color tags and
   brightness handling against the Asahi experiment and current upstream.
   The baseline confirms 10-bit scanout; qualify the firmware's PQ/BT.2020
   interpretation and identify actual panel mode and luminance capabilities.
2. Design truthful panel capability reporting and atomic HDR/SDR transitions,
   including metadata validation, SDR brightness restoration, mixed-content
   behavior and an explicit policy for panel luminance. A borrowed EDID or the
   M1 experiment's over-SDR brightness value is not a qualified J614s profile.
3. Build an isolated, reversible diagnostic kernel with the current working
   kernel and boot artifacts retained. First qualify SDR and 10-bit behavior,
   then HDR test patterns and real content, including visual transitions,
   brightness and recovery. Accurate luminance/color claims need measurement.

The exact size of the implementation and the correct HDR backlight contract
remain unknown until the source and hardware boundaries above are checked.

## Staged test

The opt-in candidate is documented in [experiments/hdr-j614s](../experiments/hdr-j614s/README.md).
It exposes a synthetic, approximate HDR panel description and tags PQ primary
surfaces on the desktop-26.6 path, without raising the existing 600-nit backlight
limit. The full `7.3.0-m4rch-hdrtest` kernel and modules built successfully,
its separate initramfs contains Apple NVMe and SART, and the independent GRUB
entry is named `m4rch experimental HDR test`. The normal kernel, initramfs,
and loader hashes were unchanged. The previous GRUB configuration was saved
on the ESP before setting the test entry as default. The next step is the
attended boot and HDR/SDR visual comparison; this candidate does not establish
firmware acceptance, brightness accuracy or HDR correctness.

## First HDR boot

The owner booted `7.3.0-m4rch-hdrtest` on 27 October. Plasma exposed HDR,
and the driver logged submission of a PQ-tagged primary surface. The owner
reported that both the desktop and HDR video looked overblown. At the first
snapshot the SDR reference was 500 nits, SDR gamut widening was 100%, and peak
brightness was overridden to 2000 nits. The physical backlight was at its
600 maximum. These settings and synthetic EDID may contribute; the log only
proves construction of a tagged swap, not correct HDR rendering.

Reducing the SDR reference to 200 nits did not resolve the reported result;
disabling wide color gamut while leaving HDR enabled also did not resolve it.
After disabling HDR and restoring the slider to 35%, the owner reported normal
colors again; the backlight returned to 211/600. The gamma-table warning also
occurred at boot, as it did on the normal kernel. These observations do not
isolate transfer-function interpretation, output-mode behavior, backlight
control, color management or application decoding as the cause.

An additional HDR comparison used Plasma's separate brightness slider at
35%, with the 200-nit SDR reference and wide color gamut enabled. The owner
reported that dark areas were far too dark and bright areas far too bright.
HDR and wide color gamut were then disabled and SDR brightness restored to
35%. This contrast error persists beyond the reference-brightness adjustment;
an incorrect transfer curve or output conversion is a candidate, not a proven
root cause. No calibrated measurement or independent firmware transfer trace
was obtained.

## Transfer-curve investigation and next-boot candidate

A controlled, fullscreen SDR gray ramp showed the missing conversion directly
in the compositor's scanout. The eight SDR gray levels 16, 32, 64, 96, 128,
160, 192 and 224 appeared as RGB10 values 64, 128, 257, 385, 514, 642,
770 and 899 in SDR. With HDR enabled at a 200-nit SDR reference, the same
samples were 29, 57, 114, 170, 227, 284, 341 and 397: essentially scaled,
not PQ encoded. KWin attached a nonlinear 257-entry gamma LUT (for example,
index 128 was 33027/65535), but the desktop DCP driver had already rejected
its firmware gamma table and logs `GAMMA_LUT ignored`. DRM nevertheless
advertised and accepted that LUT. Thus the requested transfer curve was not
applied by the hardware. This explains a concrete error in the HDR pipeline,
though it does not by itself prove the panel's PQ or color response is correct.

Current KWin uses an advertised gamma LUT for color offloading and falls back
to GPU composition when its color operations cannot be offloaded. Setting
Plasma's accuracy preference confirmed that it stopped using the LUT, but it
chose an ABGR16161616F primary framebuffer; the existing experimental HDR
admission check only accepts 10-bit RGB, and the HDR configuration was rejected.
An attempted 10-bit color-resolution preference did not change the chosen
floating-point framebuffer. Normal SDR, efficiency preference, HDR and WCG off,
and hardware backlight 211/600 were restored after these tests.

The next-boot module adds `patches/experimental-j614s-hdr-gpu-conversion.patch`
on top of the original HDR candidate. Only with the J614s HDR experiment
active, it omits the unusable CRTC gamma LUT and does not advertise the
unqualified floating-point primary format, so KWin can choose an accepted
10-bit surface for GPU color conversion. The incremental kernel module build
and existing admission/EDID/clip checks passed; these do not verify a real
atomic HDR transition or the panel. The rebuilt module is staged in the
`7.3.0-m4rch-hdrtest` module tree, and the earlier module is saved as
`/boot/appledrm-hdrtest-before-gpu-conversion.ko`. Restore it from a working
Linux boot by copying it back to
`/usr/lib/modules/7.3.0-m4rch-hdrtest/kernel/drivers/gpu/drm/apple/appledrm.ko`
and running `depmod 7.3.0-m4rch-hdrtest`. The separate normal kernel and the
saved pre-HDR GRUB configuration remain available as described above.
After reboot, verify the no-LUT and 10-bit scanout state with HDR enabled, then
compare the desktop and HDR test clip; firmware PQ interpretation, synthetic
panel primaries and peak luminance remain uncalibrated.

## GPU-conversion candidate boot

After rebooting on 27 October, the owner enabled HDR and reported that the
image looked "MUCH more reasonable" and that the color profile generally
made the screen look better. The system booted `7.3.0-m4rch-hdrtest` with
`appledrm.j614s_hdr_test=1`, and the driver logged a PQ primary submission.
Plasma reported HDR and wide color gamut enabled. The CRTC no longer exposed a
`GAMMA_LUT` property; the primary framebuffer was AR30. Repeating the same
SDR gray ramp gave neutral RGB10 scanout values 69, 126, 209, 270, 320, 362,
398 and 430, instead of the earlier 29, 57, 114, 170, 227, 284, 341 and 397.
The nonlinear increase is consistent with GPU transfer encoding now being
applied. It is not a measurement of the emitted light or proof that the
synthetic panel profile is accurate. HDR video and SDR/HDR transition behavior
still require an attended comparison; the physical backlight reported 600/600
with HDR active while Plasma's brightness slider showed 25%.

The owner subsequently reported TestUFO's WCG indicator flashing while its
HDR indicator did not. Plasma still reports HDR and WCG enabled. Chrome
156 is running with `--ozone-platform=wayland`, and its renderer has
`--enable-experimental-web-platform-features`, the flag that TestUFO requests.
`wayland-info` reports the `wp_color_manager_v1` protocol with PQ support and
an output maximum of 441 cd/m² versus a 73 cd/m² reference at the current
brightness; this is compositor-reported headroom, not a calibrated panel
measurement. The TestUFO result does not by itself establish whether HDR video
can play, and its selected rendering engine and browser canvas behavior have
not yet been identified. Further validation needs a real HDR video or a
known-good player and an attended visual comparison.

The owner later watched an SDR-versus-HDR timelapse and reported that it
seemed to work, though highlights were still somewhat blown and shadows
somewhat crushed. The source and actual encoded/negotiated video format have
not yet been confirmed, so the comparison does not establish HDR-video
passthrough. At that time Plasma's SDR reference was set to 200 cd/m² and
its saved peak-brightness override was 441 cd/m², while the panel description
remains synthetic. These values are not measurements, and changing them
without a controlled comparison would not establish the cause of clipping.

The owner identified the comparison video as
`https://www.youtube.com/watch?v=HhZNuQFn1-I` and reported its format as
SMPTE ST 2084 (PQ) / BT.2020. This establishes the reported format but does
not independently verify the browser's active decoded stream or emitted
panel luminance. The residual highlight and shadow clipping remains open.

For the planned controlled comparison, the live KScreen output confirms a
441 cd/m² peak override (synthetic EDID peak 591 cd/m²), HDR and WCG enabled,
SDR reference 200 cd/m², and automatic brightness enabled at 35%. The latter
can change the effective reference luminance during a comparison, so verify
brightness and reported Wayland luminance alongside each observation. KScreen
supports `output.eDP-1.maxBrightnessOverride.<value>`; libkscreen sends the
peak override to the Wayland output configuration independently of SDR
brightness. The owner has been asked to pause the same HDR scene before
switching to 300 cd/m²; no override change has yet been made.

The synthetic EDID sets its peak and maximum-average luminance fields to the
same encoded value (approximately 591 cd/m²). With only the 441 cd/m² peak
override applied, Wayland reports max CLL 441 and max FALL 591 cd/m², an
inconsistent description of the display. A 300-nit peak-only comparison
would leave the synthetic average unchanged and can test sensitivity to the
peak setting, but cannot independently establish a physically valid luminance
profile or rule out effects from the average metadata. KScreen's peak and
average overrides are separate controls; any paired adjustment should be
recorded as a separate experiment rather than conflated with the peak-only
comparison.

The owner compared the same paused HDR frame at peak overrides 441 and 300
cd/m² and reported no noticeable change. `kscreen-doctor` and `wayland-info`
confirmed that 300 was applied and later restored to 441; display brightness
remained 35%, reported reference luminance 73 cd/m², and the average stayed
591 cd/m². This observation does not prove the peak setting has no effect:
paused browser content may not have refreshed or reacted to the changed
output description, and the synthetic average remained inconsistent. It does
not establish a calibrated setting or resolve residual clipping.

KWin 6.8.1 `DrmOutput::createColorDescription` independently reads the peak
and frame-average overrides or EDID values and passes both into the output
color description. In this function it does not clamp the average to the peak.
This matches the inconsistent values observed from `wayland-info`. How a
particular Chrome surface responds to those values still depends on its HDR
metadata and color pipeline, and has not been traced to a visual result.
Source: https://raw.githubusercontent.com/KDE/kwin/v6.8.1/src/backends/drm/drm_output.cpp

A separate comparison temporarily set max-average to 300 cd/m² while holding
the peak at 441. Wayland confirmed max FALL 300, max CLL 441 and the same
73 cd/m² reference. The owner resumed the HDR video and reported no noticeable
change. The average override was then disabled, restoring the prior synthetic
591 value. The result does not establish calibrated luminance or rule out
browser and firmware processing; it does not support treating an average-only
override as a fix for the observed contrast.

An independent local mpv 0.41.0 test was run using signed distribution
packages extracted to a temporary directory, with no system package
installation. `gpu-next` with Wayland Vulkan decoded the generated 10-bit
PQ/BT.2020 FFV1 gray ramp. The owner reported distinct dark bands but merged
highlights. Sampling eight small gray regions of the composed AR30 framebuffer
gave approximate neutral RGB10 codes 4, 106, 231, 356, 419, 486, 558 and 601.
The last two values remained distinct in the scanout buffer even though the
owner perceived the 400- and 600-nit source bands as merged. This points toward
processing after that sampled buffer or limited perceptual separation, but is
not a calibrated panel measurement; the 600-nit source exceeds the configured
441-nit peak and mpv's tone mapping also affects the output. The test window
was closed and the display configuration left unchanged.

The owner reported that KDE's HDR calibration first-step logo was invisible
at the lowest setting. This is consistent with the reported merged highlights,
but it does not by itself locate the fault or measure peak luminance: calibration
requires a working HDR rendering and output pipeline. During the attempt,
KScreen reported a 100 cd/m² peak override and 100 cd/m² SDR reference (the
preceding values were 441 and 200); slider brightness was 47% with automatic
brightness enabled. These may be in-progress user calibration settings and
were not changed by this investigation.

## Calibration logo and transfer-tag diagnostic

KDE 6.8.1's `hdrcalibrator/Main.qml` sets the output peak to 2000 cd/m²
while the wizard is open and renders the white background and logo in
separate linear-light Wayland surfaces. With its slider at 100 cd/m², a
read-only histogram of the calibration square in the active AR30 framebuffer
showed 66,183 pixels at RGB10 code 520 in a centered 559×560 region and
524,893 pixels at code 846 in the surrounding 770×770 square. Those codes
correspond to approximately 100 and 1992 cd/m² under ST 2084; the active CRTC
CTM was zero and no gamma LUT was advertised. This strongly indicates that
the logo and its background remain distinct at scanout despite the owner's
report that the logo is invisible. It does not prove the physical panel's
transfer curve or identify the precise downstream cause.

The legacy upstream Asahi HDR trial uses the same transfer tag 16 and L10R
surface format but also forces a high raw backlight value on a different
firmware ABI; copying that raw value into the J614s nits interface would be
unjustified. For a bounded next diagnostic, the module staged for the next
boot adds `patches/experimental-j614s-hdr-transfer-probe.patch` on top of the
GPU-conversion candidate. Its default `j614s_hdr_pq_tag=1` preserves the
current PQ-tagged behavior. While the J614s HDR opt-in is active, writing 0 to
`/sys/module/appledrm/parameters/j614s_hdr_pq_tag` makes subsequent HDR
primary swaps use the driver's usual SDR transfer tag while leaving the
BT.2020 color tag alone; write 1 to restore PQ and trigger a new frame. This
is a deliberately mismatched diagnostic, not a proposed HDR fix. The screen
may look strongly wrong while it is enabled. A reboot restores the default.
The previous working HDR module is saved as
`/boot/appledrm-hdrtest-before-transfer-probe.ko`, and can be copied back to
`/usr/lib/modules/7.3.0-m4rch-hdrtest/kernel/drivers/gpu/drm/apple/appledrm.ko`
followed by `depmod 7.3.0-m4rch-hdrtest`; the normal kernel and GRUB recovery
copy are unchanged. Incremental module build, matching vermagic, existing HDR
admission/EDID/media checks, reverse patch dry-run and staged hashes passed.
The diagnostic parameter itself has not been tested on hardware. Calibration
settings were restored to the pre-test 100-nit peak and SDR reference and 15%
brightness; automatic brightness remained enabled.

## Transfer-tag comparison after reboot

The owner booted the transfer-probe module and the writable diagnostic
parameter reported `Y`. With the calibration pattern at its 100 cd/m²
slider setting, the test temporarily set `j614s_hdr_pq_tag=0` and asked the
owner to move the slider to refresh the scene. The owner reported the logo
became visible, with a mostly gray, washed-out screen. The default `Y` PQ tag
was restored and verified; the screen returned to the prior 100 cd/m² peak and
SDR reference. The calibration application had left brightness at 100% on
first check, so it was explicitly restored to the pre-test 15%; automatic
brightness remained enabled. Physical backlight continued to report 600 while
HDR was enabled.

The user-visible response shows that changing the DCP transfer tag changes
how the calibration pattern is displayed, and the SDR-tagged mismatch does
not constitute a color-correct fix. It narrows attention to the firmware
transfer/output path, but does not prove whether the HDR tag is wrong, the
firmware applies an unexpected mapping, or the SDR-only output mode/backlight
configuration prevents HDR. More evidence is needed before replacing the PQ
tag or claiming accurate HDR.

With the GPU conversion fix and normal PQ transfer tag active, a subsequent
calibration comparison temporarily disabled Plasma's wide color gamut while
keeping HDR enabled. At the 100-nit slider setting the owner reported the
logo was still invisible. Plasma confirmed WCG disabled during the test and
HDR enabled; it was restored with the previous 100-nit peak and SDR reference,
15% brightness and automatic brightness enabled. The expected connector and
DCP color tag were not independently captured during this run, and KWin's
composition also changes with WCG, so this result reduces confidence in a
simple WCG-only explanation but does not isolate firmware color conversion.

The current firmware log reports `brightness_changed: brightness value:
39321600`, exactly 600 in 16.16 fixed-point units, confirming that the DCP
received the existing 600-nit backlight request; this is a firmware-reported
value, not a measured panel luminance or proof that HDR boost is enabled.
The upstream Asahi experiment switches HDR surfaces to L10R and transfer tag
16; the current J614s path already uses those same identifiers. The older
experiment's raw brightness override belongs to a different firmware ABI and
cannot be translated into a safe or correct desktop-26.6 nits request from the
available evidence. The running firmware also logged color mode ID 1, the
same ID decoded from the SDR-only mode catalog.

## Firmware image inspection

The installed device tree reports OS firmware version 26.6.2 and system
firmware version 27.0. To inspect a matching *OS-version* DCP image without
mounting macOS or downloading a 19.8 GB restore image, the `Firmware/dcp/
t604xdcp.im4p` ZIP entry was extracted by bounded HTTP range requests from
Apple's `UniversalMac_26.6.2_25G83_Restore.ipsw`; Python's ZIP reader checked
its entry CRC. The extracted IM4P SHA-256 is
`9e161523523c7703e2fd7b8fbc8741f56d55bd48d8363036a6d4321410d643bf`;
the LZFSE payload decoded to a 10,178,560-byte arm64e Mach-O with SHA-256
`bc99f51f7b117a2af77198c061e440c7cc8232f04799ab0a53979e55c03ed925`.
The ZIP entry CRC is not an independent Apple signature verification, and the
version match does not prove that the running DCP image is byte-identical.
No firmware was modified or loaded. The extracted binaries live only under
`out/hdr-candidate/` for analysis.

The 25G83 firmware strings and disassembly contain explicit
`iomfb_enable_edr_scaling`, `iomfb_RuntimeProperty_supportHDR`,
`iomfb_RuntimeProperty_edrScaleinGP`, `GCPBypassesEDRPixels`, and an error
message for an invalid surface EDR compensation gamma. These are leads for
further ABI analysis, not evidence that any is disabled or that setting one
would fix this panel. The current kernel log does not contain that EDR gamma
error. An initial assembly inspection locates an EDR scaling boot-argument
check, but its effective runtime value and the related surface field/contract
remain unproven. The firmware logs `Could not find Backlight service` during
initialization; its relationship, if any, to HDR is likewise unproven.

## Surface ratio discovery and next diagnostic

The 25G83 arm64e disassembly gives a concrete match between the firmware's
surface object and the driver's packed `dcp_surface`: firmware reads transfer
and colorspace bytes at object offsets 0x23 and 0x24, matching the driver's
0x13 and 0x14 with a 0x10-byte object prefix. In the same path it reads two
32-bit values at 0x205 and 0x209, matching the driver's `unk_num` and
`unk_denom` offsets 0x1f5 and 0x1f9 with the same prefix. It uses their ratio
in a scaling-related calculation when certain runtime conditions hold. In one
branch equal values, including the driver's zero/zero, select unity; another
also treats a zero denominator as unity. This is strong evidence of a ratio
field but does not establish what value is correct, whether its conditional
path is active on this machine, or whether it will improve HDR.

The next-boot module additionally applies
`patches/experimental-j614s-hdr-edr-ratio-probe.patch`. It preserves the
current zero/zero surface values at boot. Only for the opt-in J614s HDR path
with the PQ tag active, the root-writable diagnostic parameter
`j614s_hdr_edr_probe` selects 0 for the existing zero/zero default, 1 for a
bounded 1/2 probe or 2 for 2/1. Other values behave like 0. Only subsequent
surface swaps pick up a change, and the parameter returns to 0 on reboot.
These probes are not calibrated corrections and may distort the picture or
risk a display fault. The previous module is backed up at
`/boot/appledrm-hdrtest-before-edr-ratio-probe.ko`, with the normal kernel
and GRUB recovery configuration retained. The module build, vermagic, existing
admission/EDID/media checks, patch reverse dry-run and staged hashes passed;
the new parameter and visual effect have not been tested on hardware.

`python3 experiments/hdr-j614s/test-surface-offsets.py` compiles the actual
candidate surface definition with static assertions for the audited transfer,
colorspace and ratio offsets, including the inferred 16-byte object prefix.
It passed along with `test-candidate.py`. This guards the layout comparison;
it does not prove the inferred prefix or ratio semantics on hardware.

## EDR ratio test

After booting the ratio probe, `j614s_hdr_edr_probe=0` and PQ tag enabled were
verified. On KDE's 100 cd/m² calibration screen, the owner reported the image
changed with the 1/2 ratio but the logo remained invisible. With the reciprocal
2/1 ratio, the owner reported that the logo was visible. Each change was
followed by moving the calibration slider and returning it to 100 to cause a
new frame. The diagnostic was restored to 0, PQ stayed enabled, and the
pre-test 100-nit peak and SDR reference, WCG, 45% brightness and automatic
brightness were verified. This is evidence that the surface ratio can affect
the physical image, not proof of calibrated output or a generally correct
ratio; the tag probe and calibration frame have not validated HDR video or SDR
content at 2/1.

## 2/1 ratio visual comparison and persistence

With PQ still enabled, the 2/1 ratio was tested on the ordinary desktop and
the owner's PQ/BT.2020 HDR video. The owner reported that desktop and video
looked improved and that neither blown highlights nor crushed shadows remained
noticeable. This follows the separate calibration observation that the 2/1
ratio made the logo visible. These are visual observations, not calibrated
luminance or color measurements; additional content and long-term stability
are not yet qualified.

The temporary timer was stopped, the 2/1 ratio was restored live and verified,
and the default experimental HDR boot entry was updated to include
`appledrm.j614s_hdr_edr_probe=2`. The previous custom entry was saved as
`/boot/grub/custom-before-edr-ratio.cfg`; restore it over
`/boot/grub/custom.cfg` from a working system to remove the boot override. The
normal kernel, the earlier module backup and pre-HDR GRUB recovery file remain
available. `grub-script-check` and copied-file hashes passed. The preceding
statement that reboot resets the ratio to zero remains true only when no
command-line override is supplied: the default experimental entry now requests
2. The boot parameter was subsequently verified through a reboot, as described below.
The live PQ tag and ratio were verified as Y and 2, respectively. HDR, WCG,
and the owner's 100-nit SDR reference and 100-nit peak override remain in use;
those values are settings, not panel measurements.

The boot parameter is compatible with the installed load path: the
`apple-silicon.service` loads `appledrm` through `/usr/bin/modprobe -a`, and
installed modprobe documentation states that it accepts module options from
`<module>.<option>` kernel command-line entries. The HDR initramfs contains no
`appledrm.ko`, so it does not shadow the staged root-filesystem module. This
supports the configuration but does not replace testing an actual reboot.

## Verification after reboot

The machine rebooted into `7.3.0-m4rch-hdrtest` with
`appledrm.j614s_hdr_edr_probe=2` on the kernel command line. The loaded
module reported ratio 2 and PQ tag enabled; Plasma reported HDR and WCG
enabled, and DCP logged submission of a PQ primary surface. The owner confirmed
that the desktop and HDR video still look improved without the earlier
noticeable blown highlights or crushed shadows. The surface-layout check,
HDR admission/EDID/media checks and GRUB syntax check passed. This verifies
the reported visual fix and its persistence through this boot, not calibrated
panel luminance, color accuracy, all content or long-term stability.

## Promotion to the main kernel

On 27 October the previously tested J614s internal HDR behavior was built
into the main `7.3.0-m4rch` kernel. It defaults to HDR support enabled and
EDR ratio 2 only on the J614s desktop-firmware internal panel; the synthetic
EDID and the physical brightness limit remain as documented above. This is
still a visually tested, uncalibrated configuration, and the associated
transfer-tag and ratio diagnostic module parameters remain available.

The source is reconstructed from Aurora `9cbdd0734d9e186c5f5f5949a21b909d10c2571b`,
the installed 7.3.0-4 patch, the four HDR experiment patches and
`patches/j614s-hdr-main-default.patch` in order. The complete installed source
patch and config are in `/usr/share/doc/linux-m4rch/`. The original kernel
configuration is unchanged. `linux-m4rch` 7.3.0-5 was built and installed;
the installed module and Image hashes match the build, initramfs includes
Apple NVMe and SART, the existing bootloader hash was unchanged after hooks,
and the HDR checks and GRUB syntax check pass. After reboot, the owner reported
that boot succeeded; the running kernel is `7.3.0-m4rch`, with HDR support and
the PQ tag enabled and EDR ratio 2 selected without HDR command-line options.
The internal eDP connector reports connected. The owner subsequently confirmed
that HDR is working and looks great on the main kernel, though it is approximate
and uncalibrated. GRUB defaults to the main entry, and the
previous GRUB configuration, which defaults to the working HDR test kernel,
is `/boot/grub/grub-before-hdr-main-promotion.cfg`. If the main kernel fails
and GRUB input is unavailable, restore that file over `/boot/grub/grub.cfg`
from macOS or recovery media. The former main Image and initramfs are also
backed up on `/boot` as `vmlinuz-linux-m4rch-before-hdr-promotion` and
`initramfs-linux-m4rch-before-hdr-promotion.img`; the prior module tree archive
is under `out/hdr-main/recovery/`. Do not extract that module archive over a
running system without planning the kernel rollback.
