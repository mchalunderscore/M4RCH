# J614s suspend and boot investigation

> Historical trial commands and diagnostic paths in this record may have been retired.
> See the [documentation index](README.md) for preserved source archives and
> the current setup; do not treat trial boot paths as current recovery instructions.

Current result: lid-close suspend and wake passed on AC and battery; the promoted standard boot entry includes the later VRR and external-display stack. The sections below record the trials chronologically. The newer [boot comparison](boot-upstream-comparison.md) describes the current standard-boot assessment.

At the start of the investigation on 27 October 2026, the running kernel was
`7.3.0-m4rch-user4k` and the installed systemd policy disabled suspend. The selected sleep state is
`s2idle`. The active T6041 Apple idle driver reports two WFI states. The
system RTC does not expose a `wakealarm`, so a timed RTC wake cannot be
assumed.

The preserved kernel source already contains the DCP message hold and
resume machinery associated with Aurora [#313](https://github.com/aurora-silicon/linux/pull/313),
and the Apple NVMe driver keeps the post-M4 ANS and its link powered during
sleep and resets queues on resume. These are source observations, not proof
that the complete J614s system can suspend or resume. Aurora's
[T6040 idle support](https://github.com/aurora-silicon/linux/pull/371) was
merged; its original test did not exercise s2idle. Aurora
[#451](https://github.com/aurora-silicon/linux/pull/451) reports a short
J616s sleep on its own kernel and loader, not this J614s stack.

The running configuration lacks `CONFIG_PM_DEBUG`, so it cannot run Linux's
staged PM tests. A separate build is prepared in `out/suspend-audit/`, using
the preserved HDR source, the user4k config and the existing GPU diagnostic
patch. Its only intentional configuration differences are PM debug and a
distinct kernel release. `tools/suspend-pm-test.sh` is intended to run the
freezer and devices stages on that kernel only. These stages exercise PM
callbacks and automatically resume without entering actual s2idle; they do
not establish working sleep, wake, or power savings. The main sleep policy
was left disabled until the subsequent lid test.

The diagnostic kernel built successfully and passed the existing native/4 KiB
userspace smoke test in an isolated KVM guest. Its 250 modules and initramfs
are staged separately, and the initramfs contains Apple NVMe and SART. The
installed Image SHA-256 is
`747e87232c144ac34f3f8e355fb09c35b90ea1e0f01ea47fbc52b9ab65facf7b`.
The GRUB entry `m4rch suspend diagnostics` was syntax checked and appended to
`/boot/grub/custom.cfg`; `/boot/grub/custom-before-suspend-test.cfg` is its
backup. At the owner's request, the diagnostic entry was initially made the
persistent GRUB default because keyboard and mouse are unavailable in GRUB.
The later promotion below selects the standard entry. A physical reset may be
needed if a test hangs; recovery without GRUB input can use macOS or recovery
media to restore the saved configuration on the Linux ESP.

## First hardware tests

On 27 October the diagnostic kernel booted on J614s. The `freezer` and
`devices` PM test stages both returned; suspend statistics showed two
successes and no callback failures. The owner saw the screen turn off and
return. A subsequent actual s2idle attempt lasted about 20 seconds wall time
from invocation to return; the owner reports waking it with a trackpad click.
Suspend statistics then showed three successes and no callback failures.
NVMe was live, root was mounted read-write, the internal connector and GPU
device nodes were present, and NetworkManager, SDDM and mbpfan remained active.
The fan driver logged three retry messages after the device test and two after
the real sleep; in both cases the fans subsequently tracked their targets. The
wireless driver also logged one transmit rejection during each transition.
The next attended s2idle cycle took about 68 seconds from invocation to return.
It also returned without PM callback failures: NVMe stayed live, root was
read-write, eDP and GPU device nodes returned, Wi-Fi reconnected and the fan
service remained active. Fan 1's unlock first returned -EIO, then succeeded;
both fans subsequently tracked their targets. Wi-Fi again logged one transmit
rejection at resume. These observations do not qualify extended or unattended
sleep, sleep energy, or every device.

The saved private evidence is in `out/suspend-audit/pm-test-20261027-01/` and
`out/suspend-audit/s2idle-20261027-01/` and `s2idle-20261027-02/`. The test
set `pm_test` back to `none`.

## Lid-close test and persistent suspend

The first lid closure was detected, but did not enter sleep. KDE's power
manager had started while suspend was disabled. After enabling suspend
temporarily, setting the AC lid action to sleep and restarting PowerDevil,
the owner closed the lid for approximately one minute. On 27 October logind
recorded lid close and KDE's suspend request at 20:34:17, s2idle entry at
20:34:18, and lid open and suspend exit at 20:35:29. The owner confirmed it
woke. Suspend statistics recorded five successes and no failures across the
two staged tests and three actual sleep cycles. Afterward NVMe was live, root
read-write, display and GPU nodes present, Wi-Fi connected, and mbpfan active;
both fans tracked their targets following two retry messages.

The owner requested normal sleep if the lid test passed. Persistent
`/etc/systemd/sleep.conf.d/90-m4rch-suspend.conf` now enables suspend while
keeping hibernation, hybrid sleep and suspend-then-hibernate disabled. KDE's
AC, Battery and LowBattery lid actions are set to sleep; the tested profile
was AC. KDE retains its external-monitor inhibition policy. The package's
older systemd restriction is overridden locally. Longer unattended sleep,
energy use, and other devices are not qualified by this one lid cycle.

## Battery report and promotion

The owner subsequently reported that lid sleep works on battery. The saved
kernel log records a lid closure and two rapid suspend attempts at 20:42:40
and 20:42:43. The first aborted with -EBUSY and no failing device identified;
the kernel reported either a device failure or an early wake event. The second
returned after lid opening. This does not establish the first attempt's cause
or a long battery sleep.

The tested Image was packaged without rebuilding as `linux-m4rch 7.3.0-7`.
The standard `Arch Linux` entry and `GRUB_DEFAULT=0` now select the main
`/boot/vmlinuz-linux-m4rch` and its matching initramfs. The Image matches the
tested diagnostic Image; the new initramfs contains Apple NVMe and SART.
The standard entry has not yet been boot-tested. The previous main Image and
initramfs are saved as `/boot/vmlinuz-linux-m4rch-before-suspend-promotion`
and `/boot/initramfs-linux-m4rch-before-suspend-promotion.img`. Its user4k
module tree was restored after package installation. GRUB and its source
configuration were saved with `before-suspend-promotion` names; the former
configuration selects the working diagnostic entry. Both `boot.bin` and
`boot.bin.old` were preserved byte-for-byte, with additional copies bearing
`before-suspend-promotion` names. Restore the saved GRUB configuration from
macOS or recovery media if the new standard entry does not boot.

Aurora [U-Boot #16](https://github.com/aurora-silicon/u-boot/pull/16) is a
draft T6040 standard EFI chain. Its post-M4 NVMe changes allocate 16 KiB
aligned TCBs and set both queue bases before controller enable; the current
local U-Boot patch uses the T6041 queue register location but derives from a
different boot and queue setup. The upstream ANS session and reserved-memory
handoff must be compared with our m1n1 and live J614s tree as a whole before
switching. The upstream report covers tethered J616s boots, not an untethered
J614s boot. The withdrawn local timeout-recovery attempt is not a safe basis
for an unreviewed reset fallback.
