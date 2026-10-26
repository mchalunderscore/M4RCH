# Native class-1 power assertion publication

The saved matched 25G83 / AGX353.14 driver supplies a missing publication step
for the planned opcode `0x0a`. `submitDeviceControl` at `0x89a6924` copies the
64-byte record, reads classification table `0x712e084`, and calls virtual
`+0xaa0` when bit 0 is set. The selected AGXArmFirmwareASC address point
`0x7ea8678` has entry `0x7ea9118`, resolving to
`incrementSchedulerGPUCorePwrAssertCounter` at `0x89b7cf8`.

That leaf loads the CPU Region C pointer from firmware `+0x380`, increments
an unaligned u32 at `+0xe51` with native modulo-2^32 arithmetic, stores it, and
executes DMB ISH. The publisher then executes another DMB ISH and publishes
`(old producer + 1) & 0xff`. Native order is record, assertion, producer.
The leaf has no explicit cache clean; Linux's retained cache maintenance is a
separate transfer, bound to the existing DMB ISH / DC CVAC / DSB SY helper.

The native 56-entry classification table matches firmware TEXT `+0x58850`.
Opcode 10 decimal (`0x0a`) has class 1. The initial root-refresh opcode 22
decimal (`0x16`) has class 0 and must leave the assertion unchanged. Firmware
`0x3900..0x3924` compares assertion with `statusB+0xe438` before dispatch and
can call activation helper `0x33a68` when they differ. Firmware
`0x5154..0x5164` increments the consumed counter for class 1 before advancing
the read cursor. Neither counter alone proves processing, GPU OFF, retirement,
or physical PMGR OFF.

Both v19/f4 and v20/09 initial and sealed precycle object captures contain
assertion 0 and consumed 0. Their root `+0x20` points to Region C at
`0xfffffc200010c000`, arena `0xc000`; root `+0xb0` points to status B at
`0xfffffc2000140000`, arena `0x40000`. No postcycle RAM capture is inferred.

The distinct v23 source corrects the frozen v22 helper with fresh Region C
pointer and baseline-equality guards, then one cache-published/read-back
assertion increment after record verification and before producer 34 and
one EP33 notification. Unsafe or ambiguous state retains ownership and refuses
further publication; there is no retry or rollback. Near-wrap baselines
`UINT_MAX-1` and `UINT_MAX` are refused before any store to preserve v22's
invalid-word rules. Native wrap behavior is understood but is outside this
trial. The original caller bool/order hypothesis, clean timeout continuation,
strict OFF checks, ownership, mappings, shader and work recipe are preserved.

New focused actual-C qualification passes 24 whole-helper RAM cases under
ASan/UBSan and composes frozen v22 CQ77 without rerunning it. Its report is
`out/gfx-native-power-assertion-fender-cycle/power-assertion-qualification-v1.json`,
SHA256 `2f92cabc0c36573b5d7fe222c01d0f509ae1dba626d7129bfeb09593f13d097b`.
The prepared source receipt SHA256 is
`3e363160308b6dba6d62a33aa058bf7e1b13da18d51f0b668f2b1c9021a8f128`.
Real build, host qualification and hardware execution are separate root-owned
steps. This source report performs no hardware access or Apple-code execution.

Full numeric source and saved-capture pins are in
`2026-10-11-gfx-native-power-assertion-publication.json`, SHA256
`06ae39b4a3bacbafb83cda84e50d159f3181819da77ffbef7d8dcf05bc7920d4`.
