# GFX native power side effects: selected paths and exclusions

2026-10-09. Focused offline follow-up to `2026-10-09-gfx-reset-native-disable-semantics`. No hardware action, API change, candidate change, or new execution harness. The companion JSON binds the matched 25G83 container, bounded native ranges, data tables, and saved boot `ce6572c9` ADT. Private bytes and full disassembly remain ignored. Findings describe the matched static inputs and their initialized paths; they do not read a live ApplePMGR object.

## GFX uses native RegMap 6, not ADT group 2

The saved descriptor for device386 has group2, offset `0x110`, flags `0x02`, byte `+0x0e=0`, and byte `+0x0f=0`. This saved ADT uses `ps-groups`, not `ps-regs`; group2's record selects ADT register54 with base offset0. That register maps bus `0x88e80000`, yielding the already qualified physical word `0x288e80110` after arm-io translation.

AppleT6041PMGR `initRegMaps` explicitly constructs native RegMap6 from ADT register54 at `0xfffffe0009c0caa0..0xfffffe0009c0cab4`. Parent initialization copies the group records and calls `_findRegMap` on their register numbers, replacing the first word with the native enum. Consequently the writer receives `(RegMap6, offset0x110)`. Comparing workaround tables to `(ADT group2, offset0x110)` would use the wrong address domain. T6041 `isPsReg` accepts RegMap6 offsets below `0x111`, including GFX.

## Both table-specific T6041 workarounds exclude GFX

The power-gate retention workaround scans ten immutable 24-byte rows at `0xfffffe00076d20c0`. Its five distinct source pairs are `(2,0x258)`, `(0,0x340)`, `(0,0x490)`, `(0,0x4e0)`, and `(0,0x2d8)`. There is no RegMap6 row. The checker therefore returns0 for GFX; the wrapper does not write a retention workaround register or enter the post-write active/BUSY waits associated with checker result1.

The AXI-to-AF workaround scans fifteen 40-byte rows at `0xfffffe000c776d90`. All source maps are0 or2, with no `(6,0x110)` entry. Its initializer fills the two mapped pointers in selected rows and its reviewed apply/quiesce/restore paths use the existing source keys. Under this matched table initialization the GFX writer cannot call `_applyAxi2afWorkaround`; enabling feature bits does not supply a missing source row. This is a static table-path exclusion, not a claim about arbitrary later corruption or unobserved platform replacements.

The saved ADT enables `pwrgateretention-workaround=1` and `axi2af-hack=0x7fff`. Those enable values do not override the address exclusions. There is no source-supported extra GFX retention/AXI register write to add from these two workarounds. The writer's separate target-zero validation path is also skipped by every proposed reset word, whose TARGET is15.

## Native level15 AUTO handling

`ApplePMGR::_setPSLevel` is bounded by `0xfffffe000982d258..0xfffffe000982db30`. When the requested AUTO policy differs from the read policy, it follows the active transition path even if TARGET is already15. For the saved ordinary active words:

* Holding AUTO first writes the read word with AUTO28 and historical bits8/9 cleared, then waits for ACTUAL15. It subsequently writes a level15 word and waits for ACTUAL15 again.
* Restoring AUTO first writes a forced level15 word and waits for ACTUAL15, then writes that word with AUTO28 set.
* These actual-state waits pass native budget `0x2ee00` to `waitReg32`. The number is a helper argument; this review does not reinterpret it as the Linux probe's microsecond budget.

The level15 transition then calls one of the generic retention methods. `_deviceIDToPowerDomainData` obtains the ID from descriptor byte `+0x0e`; zero returns null. Thus this GFX descriptor skips the power-domain sleep-depth and legacy retention paths, and calls `_setPwrGateRetentionV2(device386, true, ...)` instead.

The V2 lookup arrays at object `+0x250` and `+0xed0` initialize all800 entries to `-1`. Only `retention_config_ff` and `retention_config_mem` populate them in the reviewed initialization. Both properties are absent from the saved PMGR node. With those saved initialization inputs, both lookups remain `-1`, so the generic V2 calls perform no retention register write. A native object later changed by another path has not been observed.

`_setPSLevel` also updates an IOStateReporter channel after AUTO handling. That is native bookkeeping, not an additional GFX reset register or a DMA-retirement condition. Neither the level method nor the selected wrapper makes a PMP notification based on GFX flags `0x02` in these reviewed ranges; higher device-power methods have separate notification handling, as recorded previously.

## BUSY policy and the remaining difference

Object `+0x23bc` is the value field of feature `0x44`, named `reset-noaccess-poll`. The constructor's 24-byte feature template sets its default value0. The saved ADT lacks that property; the reviewed feature-load loop skips both its DT assignment and subsequent boot-argument override when the property is absent. This qualifies an initialized value0 for those saved inputs, not a live Apple policy value. The same template supplies the named AXI and retention features used above.

There is another conditional BUSY wait in the parent writer: object `+0xb0` bit0 and `isPsReg` enable a BUSY11-clear wait before a RESET31-set write. After a write it waits BUSY only when TARGET is below15. The former may apply to GFX; the latter does not apply to these active-target words. The direct Linux sequence already checks BUSY clear before assertion, but its polling budget and bus ordering have not been proven identical to Apple's helper.

The actual Linux native API already checks ACTUAL15 and TARGET15, AUTO held, and RESET/DEV_DISABLE/PS_RESET/BUSY clear both after inhibition and after the forced release write before AUTO restoration. It also checks active15 and BUSY clear between disable and assertion. Those predicates cover the state conditions of the relevant native active waits; an active-state check before AUTO restoration is not missing. The differences are Apple's extra forced level15 writes, its wait-helper timing/bus ordering, and any unobserved runtime policy mutation. This source review does not show that those differences cause continued firmware access.

It yields no concrete missing GFX workaround address and no reason by itself to repeat the completed trial. The new one-shot trial's live command/read evidence must decide the next action. These exclusions do not prove physical reset coverage, firmware/DMA cessation, mapping retirement, fresh DATA negotiation, restart, or safe backing release.
