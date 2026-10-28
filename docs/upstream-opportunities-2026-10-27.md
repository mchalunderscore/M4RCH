# Upstream opportunities: display, audio and boot

Review of public Aurora work on 27 October 2026. Hardware reports below are
for the 16-inch J616s, unless otherwise stated; none establishes J614s
compatibility. PR heads are moving and should be checked again before a port.

## VRR and external displays

- [Linux #451](https://github.com/aurora-silicon/linux/pull/451), open,
  extends merged [#446](https://github.com/aurora-silicon/linux/pull/446).
  It includes desktop 26.6 adaptive sync and the T6041 external display
  chain, with J616s HDMI and USB-C hardware results. The internal VRR test
  reports 24–120 Hz, but swap timing alone does not establish physical
  scanout; the author checked the panel visually. Later work adds dual-pipe
  wide displays. Review routing, lifetime and boot gating, not just the VRR
  commits. The J614s HDR/EDID modifications must be preserved.
- [Linux #515](https://github.com/aurora-silicon/linux/pull/515) is a draft
  integration on g5, whose existing internal VRR policy overlaps #451. It
  documents fallback and integration differences; it is not a drop-in patch.
- [m1n1 #56](https://github.com/aurora-silicon/m1n1/pull/56) is a draft
  ADT-derived external DCP memory handoff, plus internal display and GPU
  calibration handoffs. An earlier stage proved J616s memory handoff, gate
  stages and HDMI connector enumeration, not a USB-C display pass. Its
  newer combined stage was not hardware tested in the PR. #451's separate
  m4-loader-based tests did demonstrate HDMI and USB-C output on a J616s.
- The external-display chain must remain disabled until firmware memory and
  PMP acknowledgement are established: the author reports pre-root hangs
  if DISPEXT is powered too early. Compare the J614s ADT, topology and
  handoff against the upstream implementation before an isolated trial.

## Audio

- Merged [Linux #406](https://github.com/aurora-silicon/linux/pull/406) and
  [#419](https://github.com/aurora-silicon/linux/pull/419) provide the T6040
  AOP, J616s jack and six-speaker paths, protection interlocks and loader
  reservation contract. #406's discussion records a second J616s headphone
  and headset-mic test, plus a sleep test on an earlier version. Userspace
  dependencies include [asahi-audio #8](https://github.com/aurora-silicon/asahi-audio/pull/8)
  and [UCM #5](https://github.com/aurora-silicon/alsa-ucm-conf-asahi/pull/5).
- First check whether our existing J614 jack card and routes are present,
  then directly test headphones. For speakers, compare J614 amp topology,
  sense channels, calibration and daemon protection against the J616 work.
  A J616 speaker profile is not proof of safe J614 playback. The review
  identified unit-specific sense differences and corrected a UCM routing
  misunderstanding, so verify both protection and routing on this machine.
- HDR remains visually accepted but uncalibrated; no new upstream J614 HDR
  calibration was established by this review.

## Suspend and boot

- J616s #451 reports a 38-second s2idle with external outputs returning on
  the author's complete stack. Merged [Linux #313](https://github.com/aurora-silicon/linux/pull/313)
  supplies external resume handling and suppresses DCP message wake storms,
  tested on J700; it deliberately excludes a panel power-off approach that
  crashed DCP. Audit our exact kernel and device dependencies before treating
  those changes as a J614s suspend solution.
- Draft [U-Boot #16](https://github.com/aurora-silicon/u-boot/pull/16) adds
  T6040 ANS and EFI boot support. It reports four production-equivalent
  tethered J616s boots and an independent fresh-ANS handshake path, but no
  untethered J616s boot at the time of the report. Compare its queue,
  reservation and session handoff with our archnvme path and the withdrawn
  timeout-recovery candidate before considering a recoverable trial.

Suggested order: headphone verification; isolated internal VRR port with
fixed-refresh recovery; external DCP loader/DT/gate comparison; then integrated
suspend and boot qualification. Preserve the working boot chain for all trials.
