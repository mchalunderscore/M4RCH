# J614s HDR test candidate

> Historical candidate instructions below refer to retired trial kernels, GRUB
> entries and backups. Do not use them as current recovery instructions. The
> promoted stack supports approximate, uncalibrated HDR; see
> [current HDR notes](../../docs/hdr-investigation.md).

This is an experimental KDE/Wayland test, not production HDR support. The
candidate adds a boot-time-only `appledrm.j614s_hdr_test=1` switch, scoped to
J614s and its desktop-26.6 internal eDP controller. Without that switch its
normal SDR behavior remains unchanged. When enabled, it advertises HDR and
BT.2020 through connector properties and a synthetic EDID, and tags the
primary surface PQ (and BT.2020 when selected). It does not change DCP output
mode selection or force any brightness above the existing 600-nit limit.

The panel description is **synthetic test metadata**: nominal Display P3
primaries, a 590.7 cd/m² HDR target, an approximate 60 Hz EDID timing, and a
made-up identity. The actual display timings remain the firmware's modes.
This is sufficient to exercise KWin's HDR negotiation; it is not panel
calibration, proof of PQ correctness, or an assertion that the firmware's SDR
output-mode descriptor becomes HDR. The J614s PQ transfer tag, native/BT.2020
interpretation, overlay blending and brightness response remain unqualified.

## Candidate and recovery

Source base: Aurora Linux `9cbdd0734d9e186c5f5f5949a21b909d10c2571b`,
followed by the installed `/usr/share/doc/linux-m4rch/kernel.patch` and the
`experimental-j614s-hdr`, `experimental-j614s-hdr-gpu-conversion`,
`experimental-j614s-hdr-transfer-probe` and
`experimental-j614s-hdr-edr-ratio-probe` patches, in that order. The build is isolated with release
`7.3.0-m4rch-hdrtest`. Keep the current normal kernel, initramfs and boot loader.
The candidate remains staged as **m4rch experimental HDR test** in
`/boot/grub/custom.cfg`. The promoted `7.3.0-m4rch` main kernel is now the
GRUB default and booted successfully; its HDR support, PQ tag and 2/1 ratio
defaults are active. HDR appearance on this boot has not separately been
visually confirmed. Because keyboard input is not
currently available in GRUB, `/boot/grub/grub-before-hdr-main-promotion.cfg`
preserves the configuration that defaults to the previously verified test
kernel. If the promoted kernel fails, mount the internal ESP from macOS or
recovery media and restore that file over `grub/grub.cfg`, then sync. From a
working Linux boot, also set `GRUB_DEFAULT=m4rch-hdrtest` in
`/etc/default/grub` to preserve that choice through regeneration. The older
pre-HDR configuration remains at `/boot/grub/grub-before-hdr-default.cfg`.
A display freeze may require a forced power-off.

## Attended first test

1. Boot the test entry and confirm `uname -r` is `7.3.0-m4rch-hdrtest`.
   Check ordinary SDR desktop, input and brightness before enabling HDR.
2. In Plasma display settings, check that HDR is available; enable it for the
   internal panel. Wide Color Gamut can be tested alongside it. A successful
   switch and a usable desktop do not alone prove correct HDR output.
3. Open `pq-test.html` in Firefox and use the video fullscreen. The bands are
   neutral PQ grays at 0.01, 1, 10, 50, 100, 200, 400, and 600 cd/m²; the
   dark bands may be hard to distinguish. The associated WebM is VP9 10-bit,
   full-range, PQ and BT.2020. `j614s-pq-ramp.mkv` is a lossless FFV1 reference
   for an HDR-capable player such as mpv. Browser HDR support and decoding are
   separate variables, and visual appearance does not establish calibrated nits.
4. Try normal SDR content, move/resize windows and use Alt+Tab, toggle HDR off,
   and confirm SDR brightness and colors recover. Avoid making broad accuracy
   claims from a successful toggle or from screenshots alone.
5. Run `experiments/hdr-j614s/collect.sh` or have the agent collect the live
   KMS state and kernel log. The one-time message `HDR test: submitting PQ
   primary surface` confirms the driver constructed a tagged swap; it does not
   confirm firmware acceptance, correct output or measured luminance.

If the desktop becomes unusable, restore the saved GRUB configuration as
described above before rebooting. The HDR module parameter is off unless the
test boot entry enables it; the candidate is not suitable for promotion.

## Regeneration and checks

`python3 experiments/hdr-j614s/make-edid.py` regenerates the experimental EDID;
`edid-decode --check` checks its structure. `python3
experiments/hdr-j614s/make-pq-test.py` regenerates the sample videos using
FFmpeg. `python3 experiments/hdr-j614s/test-candidate.py` exercises the actual
connector admission function with a stubbed DRM environment, verifies the
compiled EDID bytes and checks that the browser clip's decoded luma and PQ
metadata match the intended values. These checks do not exercise kernel
concurrency, a real atomic commit, or display hardware.

On 27 October the full Image, modules and DTB build passed. The final module
declares `7.3.0-m4rch-hdrtest` vermagic and the opt-in parameter. The isolated
initramfs was built with the installed Apple Silicon configuration and checked
for Apple NVMe and SART modules. Both GRUB configurations passed syntax checks;
the staged artifacts match the build. The existing boot loader, normal GRUB
configuration, normal kernel and initramfs hashes were unchanged at staging.
The GRUB default was subsequently changed to the test entry at the owner's
request; the former GRUB configuration is saved on the ESP. The test kernel
has since been booted and exercised on the display.

## GPU-conversion follow-up

The first boot produced excessive contrast in both SDR desktop content and HDR
video. The driver advertised a gamma LUT that the firmware path actually
ignored, and KWin placed its HDR transfer conversion there. The next-boot
candidate additionally applies `patches/experimental-j614s-hdr-gpu-conversion.patch`
to hide that LUT on this opt-in panel and omit the unqualified floating-point
primary framebuffer, allowing KWin to render its transfer conversion into a
10-bit framebuffer. The previous experimental module is backed up at
`/boot/appledrm-hdrtest-before-gpu-conversion.ko`; the normal kernel and
pre-HDR GRUB recovery configuration remain separate. See
`docs/hdr-investigation.md` for measured scanout values, limitations and
restoration details. This follow-up has been boot-tested and improved the image.

## EDR ratio follow-up

The firmware reads two surface fields as a ratio in an EDR scaling path. On
the opt-in J614s HDR path, an attended 2/1 trial made the calibration logo
visible; the owner reported improved desktop and HDR video with no noticeable
blown highlights or crushed shadows. This is a visual result, not calibrated
color or luminance, and the ratio's complete firmware semantics remain unknown.

The HDR test boot entry includes
`appledrm.j614s_hdr_edr_probe=2`. The running system also has the ratio set to
2. Startup with the new boot argument has been verified, and the owner confirmed
the desktop and HDR video still look improved. To remove the
boot override from a working Linux session, restore
`/boot/grub/custom-before-edr-ratio.cfg` over `/boot/grub/custom.cfg`; to undo
the ratio in the current session, write `0` to
`/sys/module/appledrm/parameters/j614s_hdr_edr_probe` and cause a new frame.
The prior module is saved as `/boot/appledrm-hdrtest-before-edr-ratio-probe.ko`.
The pre-HDR GRUB recovery configuration and normal kernel remain available.

The main `linux-m4rch` 7.3.0-5 package now includes the same HDR behavior with
the 2/1 ratio as its J614s default. It has been built and installed but not
yet boot-tested. See `docs/hdr-investigation.md` for exact backups and checks.

`python3 experiments/hdr-j614s/test-surface-offsets.py` checks the candidate
driver's packed surface offsets against the firmware analysis. It does not
prove the inferred firmware object layout or hardware behavior.
