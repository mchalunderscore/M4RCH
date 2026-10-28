# Internal-panel VRR investigation

> Historical trial services and ESP backups described below have been retired.
> Trial sources are preserved in `out/retired-experiment-sources-20261028.tar.gz`;
> see [boot recovery](installation-maintenance.md) for the current setup.

Current result: the forced-VRR stack is promoted and firmware reports VRR enabled after wake. Physical refresh variation has not been independently verified. The following records are chronological; the first trial did not establish the final behavior.

## Attended trial, 2026-10-27

The trial kernel booted and the restore service successfully returned GRUB to
the normal default before graphics startup. The internal connector reported
`vrr_capable=1`, and HDR and wide color remained enabled at 120 Hz. KDE's VRR
policy was switched from Never to Always; the owner reported the desktop looked
normal after moving and scrolling.

The CRTC nevertheless remained `VRR_ENABLED=0`, and DCP only logged fixed
refresh modes with `VRR=NO`. Brief DRM atomic debug logging during a policy
retry repeatedly reported `CRTC:45:crtc-0 requires full modeset`. This matches
the trial driver marking a VRR change as `mode_changed` while KWin 6.8.1 tests
presentation without allowing that modeset and retries fixed refresh. The
hardware VRR path and physical variable refresh have therefore not yet been
tested. KDE policy was restored to Never and the DRM debug setting to its
original value of 0. The normal GRUB default remains in place.

Relevant KWin code: https://github.com/KDE/kwin/blob/v6.8.1/src/backends/drm/drm_output.cpp
(presentation testing and fallback) and
https://github.com/KDE/kwin/blob/v6.8.1/src/backends/drm/drm_pipeline.cpp.
Investigate a compositor-compatible modeset transition or an isolated DRM
master test before drawing conclusions about panel behavior.

Status on 27 October 2026: the forced-VRR trial booted. Firmware reported
VRR enabled at the 120 Hz mode, but physical refresh variation is not yet
independently verified. The second wake-fix trial passed one DPMS cycle and
one lid-suspend cycle. At the owner's request the trial is now promoted to
the standard Arch Linux default.

## Promotion

The owner accepted the current evidence and chose not to pursue the optical
comparison. The exact tested kernel image and display module were packaged as
`linux-m4rch 7.3.0-8`; the standard `Arch Linux` entry defaults to that image
with `appledrm.j614s_vrr=1`. Its main initramfs is byte-for-byte identical to
the boot-tested trial initramfs. GRUB syntax and the standard entry were
checked; this standard entry has not yet been boot-tested. The package includes
the four local VRR patches and the package preparation script points to the
promoted inputs.

The prior main image and initramfs are saved under `before-vrr-promotion`
names on `/boot`, along with the previous GRUB configuration and bootloader
copies. The prior suspend-test module tree was archived in
`out/vrr-promotion/previous-suspend-modules.tar.gz` and restored after package
installation; its existing GRUB custom entry is retained. The m1n1 boot files
were restored byte-for-byte after the package hook. With no GRUB keyboard,
recovery from macOS or recovery media requires restoring
`/boot/vmlinuz-linux-m4rch-before-vrr-promotion` over
`/boot/vmlinuz-linux-m4rch`, `/boot/initramfs-linux-m4rch-before-vrr-promotion.img`
over `/boot/initramfs-linux-m4rch.img`, and
`/boot/grub/grub-before-vrr-promotion.cfg` over `/boot/grub/grub.cfg`.
Restore `/etc/default/grub.d/apple-silicon-before-vrr-promotion.cfg` over
`apple-silicon.cfg` as well before regenerating GRUB. Physical refresh
variation remains unverified, and the forced mode remains compositor-unaware.

## Mode-reapply trial result

The revised module (`b038fbb9b524776029ad319a35e3df4cc462dd31b57bee43149c83054e573f0b`)
booted and the normal GRUB default was restored. After an eight-second DPMS
blank, the owner reported normal display return; firmware logged the panel HPD
completion, `VRR=NO` at 60 Hz, then `VRR=YES` at 120 Hz. The owner next
reported a normal lid wake. Kernel and systemd logs confirm approximately
60 seconds of s2idle and the same HPD, 60 Hz and 120 Hz `VRR=YES` sequence
after resume. HDR remained enabled. KWin logged one atomic `EBUSY` at each
wake, so these successful user observations are not a clean error-free log.
The firmware mode is confirmed after both wakes, but physical refresh
variation is still unmeasured; further repeated, longer and battery tests
would be needed before promoting the experimental trial to the default.

## Panel-readiness trial and mode reapply

The first wake-fix trial booted, restored the normal GRUB default and showed
`VRR=YES` at 120 Hz. The owner reported that the desktop returned normally
after both DPMS and lid sleep. The lid test slept in s2idle for about 31 seconds
after one immediate aborted attempt. Both wakes logged the panel HPD assertion
and the new completion before the VRR parameter request. However, firmware
then responded `Already set to timingID: 2 colorID: 1`, without the usual
`VRR=YES` modeset log. Thus the readiness race was addressed, but application
of the VRR parameter on wake is not established. KWin also emitted Asahi
VM_BIND and allocation errors during the DPMS wake; the owner reported the
desktop usable. Their cause and relationship to the trial are not established.

The second candidate keeps the HPD wait and, after a panel wake, selects the
matching fixed 60 Hz timing before reapplying the requested VRR-capable mode.
This sequence produced `VRR=NO` and `VRR=YES` on the hardware when requested
through KDE during the previous trial. The temporary mode is only selected
for the gated internal panel and a requested VRR mode; if no 60 Hz mode or
memory is available, or the temporary modeset fails, the requested mode is
still attempted. The module compiled with matching unresolved symbols and its
extracted implementation passed selection, one-shot, fixed-mode and failure
fallback checks; the prior wake candidate is saved as `appledrm.ko.before-reapply`.
Source delta: `experiments/vrr-reapply/reapply-on-wake.patch`. This revised
trial is armed with the existing early GRUB restore. It has not been booted or
tested on hardware; monitor DPMS and suspend logs and visual behavior.

## Wake fix and optical measurement in progress

Monotonic firmware logs show both DPMS and suspend wake requesting the 120 Hz
mode roughly 110 ms before panel HPD assertion; firmware logged an early return
with HPD and link status zero. The mode request's timing is established; an
early return does not independently establish the panel's eventual VRR state.
Aurora PR 515's external-link changes do not provide a direct internal-panel
fix; existing upstream code waits for a firmware HPD completion on Type-C.

The opt-in J614s wake candidate follows that event-based pattern: for a
previously active forced-VRR panel, power-on reinitializes a completion,
signals it on a connected internal firmware hotplug callback without changing
DRM connector state, and waits at most 1.5 seconds before the modeset. It logs
whether the callback arrived or the wait timed out. Timeout falls through to
the existing behavior, so the candidate is not a guaranteed fix and requires
hardware verification. Source delta: `experiments/vrr-wake/wait-panel-hpd.patch`.
The module built with matching vermagic and unresolved symbols; focused
callback/gate/ordering and forced-VRR tests passed. The prior forced-VRR module
is retained as `appledrm.ko.before-wake-fix`. The trial is armed, with the
same early GRUB-default restore; an early boot failure may require external
recovery. Check callback timing, timeout, firmware `VRR=YES`, DPMS and suspend.

For optical comparison, `experiments/vrr-physical/pattern.cpp` generates a
small 50-fps contrast patch, and `analyze.py` extracts center-patch brightness
from a phone recording with ffmpeg. The owner recorded a forced-VRR clip using
a 240-fps camera; the application timer had a 20.014 ms median interval over
511 updates. The supplied `IMG_0934.mov` shows the pattern, but its 1,874 stored
frames have variable playback timestamps (predominantly 23–25 ms and 47–48 ms)
and approximately 30.8 frames per playback second; it does not provide a
verified uniform 240-fps timebase. Exposure changes during the clip, and the
last part shows the desktop after the pattern closed. A representative
20-second playback interval contains 118 visible transitions with widely
varying runs. This does not establish panel refresh variation. A fixed-120 Hz
baseline recorded with the same phone and pattern is also needed. The analyzer
warns on irregular timestamps, permits choosing a playback interval, and passes
a synthetic uniform 240-fps/5-frame-period test. Observed content transitions
are not themselves direct measurements of the panel refresh clock; camera
sampling, timing and compositor scheduling can make the comparison inconclusive.

## Forced-VRR boot result

The trial boot loaded `appledrm.j614s_vrr=1`, restored the normal GRUB default
successfully, and preserved HDR and wide color. Firmware logged adaptive-sync
minimum `0x180000` (24 Hz) and `3024x1964@120 Hz ... VRR=YES`. The owner
reported normal desktop operation. KDE showed VRR as incapable and the KMS
`VRR_ENABLED` property stayed 0, as intended for the compositor-unaware
forced mode; neither property reports the firmware's actual VRR state.

An eight-second DPMS off/on cycle returned the screen and the owner confirmed
it looked normal. On wake, firmware logged an IOAV open failure followed by
hotplug and power-up, and KWin logged several `EBUSY` commits. It requested
the 24 Hz adaptive-sync parameter again, but there was no fresh `VRR=YES`
mode-set log in that wake sequence, so continued VRR after DPMS is not yet
confirmed. The boot's firmware mode log is also not independent proof of
physical variable refresh. Investigate actual scanout and wake behavior before
promotion; a physical reset goes to the normal GRUB entry.

A lid-close test subsequently spent 37 seconds in `s2idle` and the owner
reported a normal wake. As with DPMS, the 24 Hz parameter was requested while
the firmware logged the mode-selection attempt with HPD and link status zero;
there was no fresh `VRR=YES` mode-set log. KWin logged several `EBUSY` commits
at wake. A controlled 60 Hz then 120 Hz mode change produced explicit firmware
logs of `VRR=NO` at 60 Hz and `VRR=YES` at 120 Hz, leaving HDR enabled. This
demonstrates a way to re-establish the firmware mode after wake, not that it
was lost, nor that physical panel scanout is varying. Automatic wake recovery
and independent scanout measurement remain open.

## Forced-VRR follow-up

Asahi's [7.0 progress report](https://asahilinux.org/2026/04/progress-report-7-0/)
explains that VRR switches requiring a modeset conflict with the KMS contract;
KWin is acting as expected. Asahi PR 477's temporary `force_vrr` approach
enables the firmware feature during an ordinary modeset without exposing a
KMS toggle. Our earlier KMS-toggle candidate was the mismatch, not evidence
of a KWin defect. Do not remove the modeset requirement and issue a hidden
firmware modeset on an ordinary atomic flip.

The replacement adapts that approach to the current desktop 26.6 and J614s
HDR trial: when `appledrm.j614s_vrr=1`, the driver hides KMS VRR capability,
rejects KMS VRR requests, and sends parameter 14 with the valid 120 Hz mode's
minimum during a real modeset. It clears the parameter for fixed modes and
does not reuse a fixed takeover mode when forced VRR is requested. The range
is still inferred and actual physical VRR remains unverified. This is a
compositor-unaware upstream-style experiment, not equivalent to a normal KDE
VRR toggle or a production-ready solution. See
`experiments/vrr-force/asahi-force-vrr.patch` and `test-force.py`.

The module built with matching vermagic and undefined symbols; the focused
ASan/UBSan extraction test passed. It replaced only the module for the
separate `7.3.0-m4rch-vrr` trial, with its predecessor preserved as
`appledrm.ko.before-force`. The live module is unchanged. The trial's
initramfs does not contain appledrm, so it will load the staged module after
root is mounted. The GRUB entry was armed, and the early restore service
successfully returned to the normal default. An attended
boot should inspect DCP parameter and mode logs, swap completion, visuals,
HDR, and later DPMS/suspend; successful boot alone does not prove physical
variable refresh. Recovery from a display hang after the restore service has
run is a restart to the normal entry; a failure before that service may need
external recovery as described below.

## Upstream

- [Aurora Linux PR 451](https://github.com/aurora-silicon/linux/pull/451)
  is open. Its desktop 26.6 adaptive-sync work sets IOMFB parameter 14 to
  the minimum rate before selecting the mode and makes a VRR state change a
  modeset. On a J616s with 26.6.2 firmware, the author reports 24–120 Hz,
  firmware VRR enabled, completed swaps and clean on/off and DPMS tests. The
  author explicitly notes that internal-panel swap completion timing alone
  does not prove physical scanout changed; the panel was checked by eye.
  This is a 16-inch machine, not our J614s.
- [Aurora PR 515](https://github.com/aurora-silicon/linux/pull/515) is a
  draft integration of that series on g5. It says g5 already has an internal
  VRR policy and fixed-refresh failure fallback, so the overlapping PR 451
  internal commits were omitted. Its external-display boot work is separate
  from our internal-panel objective. The PR 451 review raises unresolved
  external routing and lifetime concerns; it is not a blanket qualification
  of the complete series on this machine.
- The g5 source at `1214a925` gates desktop VRR on panel capability, the
  main internal display and a failure flag, and includes a modeset fallback.
  Its full dependencies and recovery behavior still need to be traced before
  adapting it to our older base.
- [Asahi PR 477](https://github.com/AsahiLinux/linux/pull/477) and the
  [Linux 7.0 progress report](https://asahilinux.org/2026/04/progress-report-7-0/)
  describe the underlying implementation, the uncertainty in swap timestamps,
  and the KMS/compositor problem: changing adaptive sync requires a modeset.
  The Asahi work proposes an unconditional `force_vrr` option instead of
  exposing a normal userspace toggle under that contract. Aurora's approach
  is different, so KWin behavior on this particular driver must be tested.

## Installed baseline

The running `7.3.0-m4rch` has no `force_vrr` parameter. Its reconstructed
source, preserved in `out/hdr-main/source-preserved.tar.zst`, deliberately excludes desktop 26.6 VRR
from capability advertisement: a comment records a J616s black screen with
no completed swap after enabling adaptive sync. It already has parameter 14
plumbing and uses constant timestamps 1, 2 and 7 for desktop 26.6 swaps; its
comment says the architectural counter can leave swaps undisplayed after a
VRR modeset. The 120 Hz mode and actual adaptive sync are separate things.

Our main kernel also carries J614s HDR changes and a synthetic EDID. A VRR
port must preserve the HDR connector metadata, mode and surface behavior,
and ensure any VRR range presented to KWin survives EDID updates. The
installed 26.6 guard and the newer g5 policy cannot simply be bypassed
without reconciling the modeset, failure handling and timestamp paths.

## Practical next step

Compare the complete g5 internal VRR commits and their dependencies against
our reconstructed HDR-enabled source, then prepare an isolated, opt-in
J614s trial with fixed-refresh recovery and a preserved working boot entry.
Exercise parser/admission and modeset/failure tests, compile the module and
verify artifact identity before a hardware boot. During the attended trial,
capture DCP mode/parameter logs and swap outcomes, compare VRR off/on under
controlled frame rates, check HDR and SDR, transitions and DPMS, and retain a
recovery path if the panel goes black. A modeset success or compositor frame
feedback alone does not prove physical variable refresh; a suitable independent
measurement or clearly bounded visual evidence is needed. Suspend is a
separate qualification.

## Staged J614s candidate

The candidate adapts the internal-panel portions of Aurora #451 commit
`6477da65cee54d3519556b02358b8a9b3e37e99a` on the exact suspend-test source,
with a J614s-only boot-time opt-in, KMS admission checks, and parameter reply
checking. The parameter is cleared for a fixed mode as well as VRR-off; the
local HDR metadata and surfaces are retained. See
`experiments/vrr-j614s/aurora-451-j614s.patch` and its extracted-function
host test. The g5 implementation has more complete adaptive-failure retry and
swap-watchdog recovery intertwined with broader display/backlight changes;
those were not ported. A failed transport or stalled display may require a
reboot. The candidate is not a replacement for that upstream recovery work.

The source's internal 120 Hz parser infers 24–120 Hz; it is an assumption,
not a measured range for this panel. The synthetic HDR EDID remains unchanged,
and the driver supplies the range after EDID publication. KDE currently has
VRR policy `Never`, so the first trial boot can inspect capability without
requesting adaptive sync. The candidate exposes VRR only with
`appledrm.j614s_vrr=1` and only on the internal J614s display.

The isolated `7.3.0-m4rch-vrr` Image and modules built successfully; the
guest user4k smoke test passed, the initramfs includes Apple NVMe and SART,
and the focused extracted-C gate, admission, parameter and reply tests pass
with ASan/UBSan. Host EDID and lifecycle suites produced the same failures on
the unchanged source and candidate: one EDID and six lifecycle failures,
including existing stale fixtures and compiler warnings. Leak checking was
disabled due to sandbox ptrace restrictions; these suites are not clean.
Image SHA-256 `dda8059814edafa23a6a24b2689d59aaf07bfe8921624b28bb44a90dcc1ceb80`;
initramfs `5d7751a8b67c3be2ded2d0d3080e7a644657ce1a6a1a5c9e6f609362c871fbda`.

The candidate and GRUB entry were staged and `arm.sh` changed the trial's
default for the earlier boot. A systemd service restored the normal GRUB default
early in the trial boot, before graphics startup; it verifies the armed
configuration before replacing it. This is not a guarantee of recovery if
the kernel hangs before that service runs. With no GRUB keyboard, recovery
from such an early failure requires macOS or recovery media: mount the Linux
ESP and restore `grub-before-vrr-trial.cfg` over `grub.cfg`. Do not overwrite
the working main Image, initramfs or bootloader.
