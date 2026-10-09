# Matched RTBuddy / ASC restart review

This offline review binds the saved J614s/T6040 device tree to the matched
kernelcache UUID `41811D69-3027-674E-E0DB-2F6F64C70EEB`, decoded SHA-256
`6158e1c0d591240808e26ff1da050b2fa0ed3eb17c1779d2ddde3171b959536f`.
The companion JSON records exact VM ranges, root-segment file offsets, hashes,
selected encoded vtable words, saved-log lines, and the device-tree properties.
Private binaries and disassembly remain in ignored `out/private-apple/`.
No hardware action, module deployment, wake trial, or reboot was performed.

## Actual provider selection

Saved ADT `/device-tree/arm-io/gfx-asc` is compatible `iop,ascwrap-v6`, role
`GFX`, version 1. Its nub matches `iop-nub,rtbuddy-v2`, with `pre-loaded=1`
and empty `no-firmware-service` and `shutdown-sleep` properties. Matched
personalities select generic `AppleASCWrapV6` and `RTBuddy`; they do not select
`AppleASCWrapV6SISP`, `RTBuddy64`, or the SEP wrapper. These are static matching
and property-construction inferences, not a live macOS IORegistry capture.

ASC register ranges are ADT offsets `0x8a600000/0x88000` and
`0x8a050000/0x60000`; saved arm-io translation adds `0x200000000`.
Absent `cpu-ctrl-filtered` selects native control writes (+132=1); absent
`no-activate-mapper` selects mapper activation (+133=1). Absent
`idle-ctrl-check` means the optional CTRL40 bit0 test is disabled.

## CPU control and observed values

V6 `_runCPU(false)` (`0xfffffe0008a3fcf4..8a3fda4`) reads CTRL44, clears
`0x10`, reads CTRL44 again, then clears `0x20`. `_runCPU(true)` only reads
CTRL44 and writes that value OR `0x10`. It neither sets nor tests `0x20`, and
does not inspect status or program a reset vector. Both branches are gated by
the native +132 property policy.

Old owner helpers stop by writing the saved entry control AND NOT `0x10`.
That is a code difference, **not an established causal recovery difference**:
the bounded saved-log search recorded only CTRL44 `0x0` and `0x10`; no sample
has `0x20` set. Warm START failed at control0/status6e, and START+INIT220
failed at control0/status48. Running failed-trial telemetry includes
control10/status6c. The logs do not sample every instant, but they provide no
reason to retry only an extra bit20 clear.

V6 `_isIdle` (`8a3fc54..8a3fcf4`) returns `(STATUS48 & 3) != 0`, requiring
**either** bit0 or bit1, with optional CTRL40 bit0 gating only when +1a0 is set.
Thus recorded 6a/6e/4e pass this narrow native predicate, while 6c/48 do not.
It is not a DMA retirement predicate. Common `stopCPU(bool,bool)` polls
initially and up to ten more times after `IOSleep(1)`. Generic AppleA7IOP
construction sets +109=1; failed idle polling then takes the panic path.
The first "force" bool does not bypass idle polling. The distinct SISP
initializer clears +109, but that class is not selected for this GFX node.
Consequently the native force-off call is not a checked rescue recipe for
our observed nonidle wedge.

## Power states and restart selection

Matched management `requestPowerState` sends table entries:

| Native requested state | Endpoint-0 word |
| --- | --- |
| 0 (SLEEP) | `0x0060000000000201` |
| 1 (ON) | `0x0060000000000220` |
| 2 (PWRGATE) | `0x0060000000000202` |
| 3 (OFF) | `0x0060000000000000` |

Native PWRGATE2 waits for IOP status2 and calls `stopCPU(false, second_bool)`;
the second bool is zero in the ordinary nonhibernate path. The common stop
then stops the core, calls `_unmapFirmware`, deactivates the mapper when
policy +133 permits, and disables the provider power domain. These framework
calls do not establish physical power-off readback or device-wide GPU reset.
Linux RTKit's IDLE201 retains state and does not perform this CPU-stop path;
its `wake` INIT220 alone does not implement native PWRGATE202.

Force-off changes native IOP bookkeeping to status1 and clears fixup-done
+10b. On the next native ON, prior status1 or2 selects `startCPUWithOptions`
options0 (or2 if the native running flag +2231 is set). Prior status3 selects
options bit0=1 and the management `wakeQuiesced` path. Options bit0 controls
whether the native start powers the provider, maps firmware, and runs the
CPU; these are separate from the management INIT220 value. Actual nub
`running` is absent, so the saved-property inference is options0 for a
stopped status1/2 route. The complete cold restart remains unproven.

## Preloaded memory and SRAM limits

V6 `_mapFirmware` calls `_dartMapiBootFirmware` for saved iBoot segment
metadata, unless options bit1 skips mapping. The native mapper routine skips
when +130 is already set, the mapper is null, segment metadata is null, or
the mapper lacks its required property. Its record layout is 32 bytes:
physical address +0, another address +8, mapper IOVA +0x10, size u32 +0x18,
flags u32 +0x1c. The two actual saved records have nonzero sizes `0x60000`
and `0x138000`; nullable pointers or zero-size descriptors must not be
invented to reproduce this route. Native range allocation/map calls do not
copy DATA bytes or program an ASC reset vector. `_unmapFirmware` releases
only optional +198; it does not clear retained iBoot mapping flag +130.
The startup property load initially clears +130, so a repeated map call may
deliberately be a no-op after the first native start.

Preloaded firmware sets iBoot-loaded +c0=1; `Firmware::fixup` then skips its
`copyToTarget` branch. `no-firmware-service` selects direct preloaded loading
and bypasses service matching. It does **not** alone prohibit the separate
`reloadFirmware` API: that API's +d0 gate is instead
`rtb_disable_fw_load OR (disable-in-restore AND -restore) OR disable`.
Reload requests native OFF3 and selects preloaded metadata if +2230 is set;
this is not proven to reset a wedged firmware or restore mutated DATA.

There is a separate conditional SRAM save/restore path. Its enable flag
+2244 is true if the provider requests `should-control-sram` or a parsed
segment needs backup. Native segment flags map saved ADT flagbit2 to the
`needsBackup` bit. Actual TEXT flags1 and DATA flags0 therefore need no
backup. AppleA7IOP initializes its SRAM mask +15c=0 and only loads/publishes
`should-control-sram` from present `sram-index`; that property is absent on
the actual saved GFX node. This static contract leaves +2244 false, skipping
the conditional saved-memory copies. `enableSRAM(bool)` with mask0 returns
`0xe00002e2` without provider power mutation. Force-off nevertheless calls
it false; RTBuddy's wrapper ignores the returned status. This call supplies
no missing DATA restore or additional SRAM reset for the saved GFX setup.

The meaningful unresolved scopes are the physical effect and completion of
the provider power operation and mapper `setActive(false/true)`, plus a
checked route that can stop the currently nonidle CPU. This review qualifies
native code and configuration, not successful restart, firmware reload,
DMA retirement, GFX PMGR reset coverage, or permission to free caller pages.
