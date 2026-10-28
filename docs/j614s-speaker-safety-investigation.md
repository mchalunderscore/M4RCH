# J614s speaker safety assessment

Assessment on 2026-10-27. This is a read-only comparison, not speaker enablement or a hardware safety certification. The raw Apple device tree (ADT) used here was captured earlier from this machine and is retained privately under `out/external-investigation/private/current.adt`. The [audit](../experiments/speaker-safety/audit-adt.py) extracts only audio-related metadata; its [result](../experiments/speaker-safety/j614s-adt-audit.json) excludes the rest of the ADT. No amp, GPIO, mixer or PCM was changed and no audio was played.

## J614s hardware and J616s comparison

The J614s ADT describes six `audio-control,sn012776` devices. Following the primary amplifier's `speaker1`–`speaker5` phandles gives the order below. The primary node does not name its speaker; left woofer 1 is the J616s board's corresponding label, consistent with the other five names, but is still a hypothesis for this specific unit.

| Order | J614s ADT node | I²C bus/address | RX slot | Raw sense slots |
| --- | --- | --- | --- | --- |
| 0 | `audio-speaker` (likely left woofer 1) | i2c1 / 0x38 | 0 | 0, 2 |
| 1 | right woofer 1 | i2c3 / 0x3b | 1 | 4, 6 |
| 2 | left woofer 2 | i2c1 / 0x39 | 2 | 8, 10 |
| 3 | right woofer 2 | i2c3 / 0x3c | 3 | 12, 14 |
| 4 | left tweeter | i2c1 / 0x3a | 4 | 16, 18 |
| 5 | right tweeter | i2c3 / 0x3d | 5 | 20, 22 |

These addresses, ordered labels, playback slots and raw pairs match Aurora's [J616s device tree](https://github.com/aurora-silicon/linux/blob/integration/aurora/arch/arm64/boot/dts/apple/t6040-j616s.dts). All six J614s config entries have raw gain 15; the first two `amp-tx-zd-config` words match the zero-fill masks used by Aurora. Its primary amplifier node has `speaker-protection = 1`, reset GPIO 54 and interrupt 55 on the main GPIO controller, consistent with the J616s tree's shared shutdown and fault wiring. These are descriptions, not live electrical tests of the individual amplifiers or interrupt polarity.

**Sense ordering needs explicit reconciliation.** The [m1n1 ADT parser](https://github.com/aurora-silicon/m1n1/blob/1efafe1fe0ec134b89d55c2cc64106a66a4df2b7/proxyclient/m1n1/adt.py) labels the third and fourth configuration bytes `vsense_slot` and `isense_slot`. Aurora's J616s DTS instead assigns the corresponding first and second raw slot numbers to `imon` and `vmon`, respectively, and its J616s `speakersafetyd` configuration uses current then voltage. The representations may use different conventions, or a label may be wrong; neither possibility is established here. Do not derive the working J614s sense polarity solely from either label. Verify the complete serializer/codec layout against the J614s and protection consumer before enabling playback.

## Parameters

The saved J614s ADT contains a 138-byte `speaker-thiele-small` property. Using the m1n1 parser's layout, it has six records `spA0`–`spA5` whose `r_mohm` fields are 3666, 3695, 3753, 3756, 3704 and 3715. The record labels' relationship to physical channels has not been independently verified; raw temperature fields and checksum semantics are also not established. These values cannot be treated as a complete thermal model or substituted directly for a profile's nominal impedance.

Aurora's [J616s safetyd profile](https://github.com/aurora-silicon/fedora-aurora/blob/main/packages/speakersafetyd-aurora-profiles/j616.conf) uses the older 16-inch J316 model parameters with a J616s-specific channel map. The [14-inch J314 profile](https://github.com/AsahiLinux/speakersafetyd/blob/main/conf/apple/j314.conf) and J616/J316 profile have materially different thermal constants and nominal impedance. Neither family has been shown here to match J614s speakers, so neither profile is qualified for copying. Apple data used by macOS's feed-forward model must not be assumed directly equivalent to speakersafetyd's feedback thermal model. The ADT resistance entries alone do not establish coil/magnet thermal resistances, time constants, temperature limit, shunt, scaling, or the right model family.

Aurora's [J616s tests and discussion](https://github.com/aurora-silicon/linux/pull/406) report a low current sense on one unit's left woofer while two others read normally. The test profile links gains and its graph duplicates the left woofer signal; that mitigation depends on the routing and cannot be assumed to cover an arbitrary mismatch on J614s. The actual amplifier-fault shutdown was checked by code and probe rules, not a real amp fault. Aurora also reports a [warm-restart issue and fix](https://github.com/aurora-silicon/fedora-aurora/pull/23): a daemon restart must not incorrectly initialize a hot speaker as cold.

## Current live configuration

The current Linux DT has all six amp nodes, the shared shutdown regulator and speaker sound card **disabled**. The AOP audio node exposes only `dma`, `cout`, `cin`, without `spkr` and `sense`; the live ALSA cards are the internal microphone and headphone jack. The amp module is blacklisted and `snd_soc_macaudio.please_blow_up_my_speakers` reads `0`. The loaded macaudio module serves the separate headphone card; its presence alone does not mean the speaker card is active.

The local tree already contains Aurora's speaker stream code and a disabled J616-shaped speaker node. However, the sound card is labelled J616 and its sound identity, UCM, graph, daemon profile and speaker/sense DMA must not be enabled as-is merely because wiring looks similar. The AOP handoff and separate jack/microphone services must remain intact.

## Work needed before a safe port can be claimed

1. Establish J614s speaker part/tuning family and defensible model parameters, including coil and magnet thermal behavior, limits and scaling, with authoritative device-specific evidence or appropriate measurement. Compare the 14-inch and 16-inch profiles; do not claim the ADT resistance records prove either one. Determine whether additional machine-specific macOS assets or hardware documentation are available and what their values mean in this daemon's model.
2. Resolve the ADT/driver sense-label discrepancy and establish every J614s playback-to-amplifier and V/I channel mapping, sign, scale, frame alignment and shared bus idle mask. This must include a plan for unit-specific bad sense values and must not assume the J616s grouped-gain mitigation always covers them.
3. Adapt board-specific DTS/card naming and AOP DMA while preserving the current headphone, microphone, boot and suspend paths. Keep amps and speaker card disabled in normal boots. Confirm the exact installed kernel includes the fixes from [Aurora #406](https://github.com/aurora-silicon/linux/pull/406) and follow-up [#419](https://github.com/aurora-silicon/linux/pull/419), including shared-SDZ handling, sensor ring alignment, suspend locks and the lease-timeout fail-closed behavior.
4. Audit interlocks and failure handling end to end before any speaker output: absent/wrong controls, missing or bad sense data, daemon exit/freeze/crash/restart, UCM or DSP failure, card rebind, suspend/resume and amp faults. In the checked local `macaudio_vlimit_unlock`, no matching volume control is logged but the SN012776 lock-failed flag is only set for a failed lock operation; determine whether the missing-controls state is reachable and make it fail closed if it is. Tests need to exercise actual signal and protection paths, not just daemon presence or a successful ALSA open.
5. Only after those evidence gates, develop a separate, recoverable validation plan with appropriately qualified protection and measurement. A normal volume slider, generic `-20 dB` number or low-volume setting alone is not a proven safety boundary. The machine-specific risk cannot currently be quantified, and this assessment does not authorize playback or activation.
