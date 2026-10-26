# Native GFX PMP/PMC coordination — 2026-10-09

Offline review of the complete matched 25G83 kernelcache and the saved a1 ADT resolves two selected native coordination steps around physical GFX power transitions. GFX OFF updates the PMP dashboard and waits conditionally for its acknowledgement, then clears a PMC rail vote, before writing physical target 0. GFX ON performs those corresponding enable operations after physical target 15. A PMGR target transition alone does not establish either boundary.

The machine was not accessed. No source, owner, kernel API, candidate, boot or hardware changes were made. The prior [mapper-terminal evidence](2026-10-09-gfx-mapper-terminal.md) and [independent live OFF review](2026-10-09-gfx-poweroff-live-review.md) remain unchanged. This result does not reinterpret the retained bit11 or the continued firmware-owned counter writes.

The paired [JSON receipt](2026-10-09-gfx-native-shutdown-coordination.json) pins input hashes, bounded native ranges, initialized data, actual vtable bindings and selected ADT records. Private bytes and full disassembly stay under ignored `out/private-apple/`.

## Selection and ordering

The initialized ApplePMGR feature table has 97 records of 24 bytes, copied from `0xfffffe0008185b60` to object offset `0x1d50` by the constructor. Startup loads named DT properties and records their presence/value. The saved `pmp=2` supplies object mode `+0x1bd8`; actual T6041 `_pmpV2` compares that field to 2. A native `pmp` boot argument can override it. The saved `pmc=1` supplies feature85 and cannot be overridden by the top-level T6041 feature method.

Notifications require a changed native direct vote and a changed aggregate GFX386 record. Other native votes can prevent the aggregate change; no runtime vote state is available. For the saved GFX flags `0x02`, the exact phase predicates select:

| Request | Native ordering |
| --- | --- |
| `_enableDevice(401,0,0,0)` | PMP command14 `{u64 device386, u64 enabled0}` at `0xfffffe000984d2e4`; PMC notify `(386,false,0)` at `0xfffffe000984d344`; physical sync at `0xfffffe000984d4c0`, including GFX target0. |
| `_enableDevice(401,1,0,0)` | Physical sync at `0xfffffe000984d4c0`, including GFX target15; PMP command14 `{u64 device386, u64 enabled1}` at `0xfffffe000984d630`; PMC notify `(386,true,0)` at `0xfffffe000984d69c`. |

The caller does not inspect either notification return status. Virtual401 lacks the PMP selection bit and has no matching PMC agent row. The saved 401→386→385 chain does not select the earlier `_checkNotifyPMP` readiness wait: its flags lack the required `0x82` combination, and its descriptor performance-domain indices resolve null. The selected dashboard acknowledgement is the concrete wait here.

## PMP dashboard payload and acknowledgement

PMP2 command14 dispatches to `_pmpWriteDashBoardSetDeviceState`, using an initialized `ApplePTD` helper owned by ApplePMGR. It does not require `function-pmp_control` or a selected mailbox packet. Initialization reads the saved `/arm-io/pmp/iop-pmp-nub` metadata. The `ptd-ranges` selectors are `[10,11,12,13,2,4]`; the required request, acknowledgement and status pointers resolve to existing records. GFX descriptor legacy index14 maps to `soc-device` row13, named AGX, whose flags are `0x3`. Its request bitmap mask is therefore `1ULL<<13`, or `0x2000`.

Native RegMap8 maps saved pmgr reg50, bus `0x3003c0000`, size `0x30000`. The saved arm-io translation adds `0x200000000`, yielding physical base `0x5003c0000`.

| PTD record | First entry | Native access offset | Derived physical address |
| --- | ---: | --- | --- |
| SOC-DEV-PS-REQ, ID10 | `0x1e0` | Read `0x1e00`; write `0x10f00` | Read `0x5003c1e00`; write `0x5003d0f00` |
| SOC-DEV-PS-ACK, ID11 | `0x1e8` | Read `0x1e80` | `0x5003c1e80` |
| PMP-STATUS, ID2 | `1` | Read `0x10` | `0x5003c0010` |

The read helper uses `LDP` for two 64-bit words at `base+entry*16`. The first word is the full payload and is returned unchanged. For the raw second word `S`, the returned status is `(S>>10) | ((S&1)<<55) | (((S>>1)&1)<<54)`, plus the preserved output byte15. The ACK test of returned bit54 therefore tests **raw second-word bit1**, not a bit in the request payload.

OFF writes `oldREQ & ~0x2000`; ON writes `oldREQ | 0x2000`, preserving all other request bits. The write helper passes this full 64-bit payload to `writeReg64` at `base+0x10000+entry*8`; the lower helper performs a `STR` of that word. No status encoding is appended. Native OFF does not require request bit13 to have been set initially.

GFX row flags bit1 selects a wait for both directions; bit2 is clear, so ON does not take the enable-side skip. The native success predicate is:

`PMP_STATUS.payload == 0 OR (ACK.raw_status.bit1 == 1 AND ((ACK.payload XOR writtenREQ) & 0x2000) == 0)`.

There is no raw-validity check on the request or PMP-STATUS payload reads in this path. A zero status payload skips ACK; the reviewed code does not establish that zero means safely inactive. Native mode2 is an object field, and no equivalent hardware mode/readiness register has been qualified.

The total deadline uses `clock_interval_to_deadline(15,1000000000,...)`, equivalent to 15 seconds in the native clock conversion. The loop also computes a `(100,1000000)` deadline, but does not consume it or call a sleep, delay or yield. Timeout reads the PMPOOL diagnostic range and panics; it does not produce a successful acknowledgement. Missing request/ACK/status pointers return `0xe00002bc`, and an unmapped device index returns `0xe00002c7`; those returned statuses are ignored by the outer notification caller.

No explicit DMB/DSB, acquire/release instruction or write readback occurs in the bounded selected PTD access functions. This does not prove the wider memory-mapping or ordering contract, nor justify copying raw accesses into a Linux spinlock-held PM callback.

## PMC rail voter

The actual initialized object is static `AppleT6041PMC` at `0xfffffe000c777020`, reached through the matched T6041 getter and `stateChange` vtable. The saved `pmc-pmgr=0x3f` selects dynamic-interface support bit0. Individual `pmc-pmgr` override is disabled, but `_getPMCFeatures` checks the global native `pmc` boot argument: `pmc=0` clears each loaded support value. That runtime boot argument is unobserved.

The saved type2 GFX386 voter-agent row selects agent bit2, rail mask7, and the DCS/SOC/DISP_INT rail records. Native RegGroup34 maps RegMap129 plus offset `0x800000`; RegMap129 maps ADT reg60, translated to physical base `0x504000000`. The three full 32-bit enable words are `0x5048ac000`, `0x5048ac004`, and `0x5048ac008`.

OFF reads each word and writes `old & ~0x4`; ON writes `old | 0x4`, preserving unrelated voter bits. The lower access is a 32-bit LDR/STR with no appended status encoding. The selected branch has no explicit ACK wait, readback or mailbox-state wait. Map129 is excluded by actual T6041 `isPsReg`, so these writes do not select PS bit11 waits. Other PMC interfaces have positive saved lookup rows that exclude GFX386 and virtual401.

## Meaning and limits

The new actionable boundary is a **paired, owner-coordinated PMP/PMC enable and disable protocol**, surrounding the physical PMGR transition in the native order. Runtime request, ACK, status, vote and support-policy values remain unavailable. The evidence qualifies an offline implementation comparison; it does not authorize raw writes or prove that the missing steps cause the observed failure.

PMP acknowledgement is a platform coordination result. It is not a GPU cache/UAT/DMA retirement fence, backing-release authority, reset proof or rendering readiness. The existing failed OFF result remains frozen.
