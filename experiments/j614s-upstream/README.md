# J614s upstream work

The installed stack is built from the [Aurora ALARM fork](https://github.com/mchalunderscore/alarm-aurora/tree/j614s/full). See [current status](../../docs/status.md), [hardware status](../../FEATURES.md), [update workflow](../../docs/aurora-update-workflow.md), and [recovery](../../docs/recovery.md). Combined-stack tests do not establish that each upstream branch works independently.

As checked on 2 November 2026, [Linux board support #795](https://github.com/aurora-silicon/linux/pull/795), [board identifiers #816](https://github.com/aurora-silicon/linux/pull/816), and [SD support #818](https://github.com/aurora-silicon/linux/pull/818) are merged. These proposals remain open:

- [Linux GPU #804](https://github.com/aurora-silicon/linux/pull/804) and [Aura MCC #43](https://github.com/aurora-silicon/aura/pull/43): the 16-core GPU layout and preemption remain unqualified; see [context observation](../j614s-gpu-context/README.md).
- [Linux retained input #817](https://github.com/aurora-silicon/linux/pull/817) and [U-Boot #29](https://github.com/aurora-silicon/u-boot/pull/29); [Aura display #44](https://github.com/aurora-silicon/aura/pull/44), [root address resolution #45](https://github.com/aurora-silicon/aura/pull/45), and [cooling references #46](https://github.com/aurora-silicon/aura/pull/46).
- Firmware and device handoffs: Aura [AOP #47](https://github.com/aurora-silicon/aura/pull/47), [ISP #48](https://github.com/aurora-silicon/aura/pull/48), [USB tuning #49](https://github.com/aurora-silicon/aura/pull/49), [SEP reservations #50](https://github.com/aurora-silicon/aura/pull/50), [ANS reservations #51](https://github.com/aurora-silicon/aura/pull/51), and [HDMI tuning #53](https://github.com/aurora-silicon/aura/pull/53); [Linux ISP #821](https://github.com/aurora-silicon/linux/pull/821) and [installer firmware #71](https://github.com/aurora-silicon/aurora-installer/pull/71).
- [Linux GPU thermal #852](https://github.com/aurora-silicon/linux/pull/852): exploratory, with hot-load behavior and limits unqualified. See [hardware limitations](../../docs/hardware-limitations.md).
- [Mesa #138](https://github.com/aurora-silicon/mesa/pull/138): see the [hardware reproducer](../mesa-zink-surface/README.md).
- [UCM #9](https://github.com/aurora-silicon/alsa-ucm-conf-asahi/pull/9) and [audio DSP #16](https://github.com/aurora-silicon/asahi-audio/pull/16): microphone support. Speakers remain disabled pending a qualified J614s-specific protection profile.


Current hardware risks and qualification gaps are summarized in [hardware limitations](../../docs/hardware-limitations.md).
