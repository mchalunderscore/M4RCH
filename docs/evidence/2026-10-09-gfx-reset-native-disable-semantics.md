# GFX DEV_DISABLE readback: matched native sequence and the next boundary

2026-10-09. Offline analysis only. No hardware, kernel, owner, boot, or module changes. The companion JSON pins the qualified Linux tree, saved first trial, current-boot ADT, matching 25G83 kernelcache, sparse disassembly, and bounded native function ranges. Private driver bytes and full disassembly remain under ignored `out/private-apple/`.

The first checked API trial stopped at an added expectation that DEV_DISABLE bit 10 must read back set. It did not reach the RESET bit 31 assertion update. The matched Apple path supports a concrete alternative: preserve a command image, explicitly write disable and combined disable/reset, and use the selected native timing or BUSY boundary without requiring either command bit to latch. This is a lead for a separately qualified candidate; it does not establish that GFX reset works or retires GPU/ASC access.

## Saved first attempt

Boot `ce6572c9-2491-4c87-8e27-6e82cc0ac657`, candidate v2, one no-work attempt after mandatory shadow validation. The saved result is `-110` (`ETIMEDOUT`), valid mask `0x87`:

| Observation | Value | Meaning |
|---|---:|---|
| BEFORE | `0x1f0003ff` | ACTUAL/TARGET active 15; AUTO bit 28 set |
| AUTO_HELD | `0x0f0003ff` | Current API's direct AUTO hold observed |
| DISABLED last poll | `0x0f0003ff` | Bit 10 did not read back set |
| ASSERTED | invalid | The reset assertion update was not reached |
| CLEANUP_FINAL | `0x1f0003ff` | Cleanup error 0; original AUTO observed restored |

Read-valid marks a captured value, not command acknowledgement. The timeout therefore tests the checked API's disable-latch predicate, rather than physical reset coverage. The root subsequently sealed the gate and performed the packet-free stop; retained backing remains owned. Neither this result nor ASC idle/START clear permits freeing mappings or backing or restarting firmware.

## Comparison to existing reset implementations

The qualified Linux `apple_pmgr_reset_assert()` writes DEV_DISABLE, then RESET, with no bit-10-set poll. Deassert clears RESET, then DEV_DISABLE. These are fresh `regmap_update_bits()` operations; when a preceding command bit reads clear, a later RMW can omit that command bit. Linux's force-disable power-off path has other status checks, but that is a different path from the generic device reset operation.

The maintained local m1n1 reset similarly sets disable, sets reset, delays 10 microseconds, then clears both through successive operations. It supplies no bit-10-set acknowledgement requirement. The current checked API added that requirement and timed out before reaching reset.

## Selected matching Apple path

The matching ApplePMGR `_setPSReset` range is `0xfffffe0009841834..0xfffffe0009841ca4`. It first requires TARGET low nibble 15. When original AUTO28 is set, it calls `_setPSLevel(..., level=15, auto=false, ...)`, then reads the register again. It later restores original AUTO through `_setPSLevel(..., level=15, auto=true, ...)`. These are native level-method calls with their own power handling; our current direct AUTO-bit update is not evidence that the two procedures have identical side effects.

Let `B` be that fresh native read with historical bits 8/9 cleared (`read & ~0x300`). The saved GFX descriptor selects these explicit command words:

| Step | Intended native write | Following boundary |
|---|---|---|
| Disable | `B | 0x400` | Object field `+0x23bc` nonzero: wait BUSY11 clear; otherwise `IODelay(1)` |
| Assert | `B | 0x80000400` | Saved descriptor `+0x0f` bit 5 clear: `IODelay(1)` |
| Release | `B` | No RESET31 acknowledgement branch for this descriptor route |

The disable boundary uses `waitReg32(mask=0x800, expected=0, budget=0x2d0)` when its native policy is enabled. It does not poll bit 10 set. The actual native object value at `+0x23bc` has not been established live. The alternate descriptor-bit-5 route has additional wait/deassert steps; it is not selected by the saved GFX record and should not be transplanted as the current route.

Using our observed held value only to illustrate intended command images gives `B=0x0f0000ff`, disable `0x0f0004ff`, combined assertion `0x8f0004ff`, and release `0x0f0000ff`. A fresh RESET-only RMW after bit 10 reads clear can instead produce `0x8f0000ff`. Thus simply deleting the new bit-10 poll would still miss a native distinction: the assertion explicitly includes bit 10 from a preserved image. These are source-derived command values, not captured live bus writes.

The T6041 constructed vtable resolves the native calls to the AppleT6041PMGR `writeReg32` wrapper at `0xfffffe0009c11acc..0xfffffe0009c11e94`, then the ApplePMGR parent writer at `0xfffffe000983cee0..0xfffffe000983d09c`. The parent performs the raw 32-bit store at `0xfffffe000983cfb8`. The wrapper passes the desired word unchanged and introduces no DEV_DISABLE-set poll. It is not universally a plain-store wrapper: native configuration can enable retention and AXI-to-AF workarounds, additional power-status waits, and notifications. The explicit target-zero power path is skipped by the derived active-target words, but applicability of the other wrapper policies to this GFX register remains unqualified. No security/PMP proxy requirement for this reset write was established by this bounded review.

The parent wait helper at `0xfffffe000983d09c..0xfffffe000983d2a4` compares `(read & mask) == expected` with bounded timing/timeout behavior. It does not turn a valid read into an acknowledgement. Constructor, address-point, slot and function-byte pins are in the JSON; parent-vtable offsets account for the 16-byte header rather than confusing child slot `0x1068` with the parent write method.

## GFX flags and descriptor route

Current-boot ADT record 274 is the real GFX device 386: flags `0x02`, group 2, offset `0x110`, descriptor byte `+0x0f=0`. Its qualified physical mapping is `0x288e80110`. AFR/GPX have flags `0x09`; GFX-SGX and GFX-ASC have virtual/no-PS flags `0x10`.

The maintained m1n1 flag map names bit 1 `notify_pmp` and bit 4 `no_ps`. The matched native `_resetDeviceGated` rejects bit-4 virtual devices, with no bit-1 reset-capability rejection in the reviewed path. Native power methods have bit-1 notification handling. Consequently flags `0x02` do not presently support a claim that GFX cannot be reset. Native initialization loads 48-byte `devices` records, allowing a `devices_%u_%u` override; the saved ADT has only `devices`. The saved byte-0x0f route therefore comes from the original descriptor, not an assumed transformed flag.

## Next bounded candidate and remaining proof gaps

A future candidate must be a separate API/version, kernel build, and qualified receipt. Preserve powered-domain/runtime-PM and reset-user exclusion checks, retained ownership, no submitted work, one attempt, and permanent sealing. Keep command-attempt bits, desired words, write errors, read-valid bits, readbacks, delay/BUSY results, cleanup attempts/errors, and AUTO rollback as separate evidence. A completed command sequence must not be labelled reset-acknowledged when its command bits do not latch.

The candidate should use explicit combined assertion and explicit release writes from a preserved image; a fresh RMW or an elided release cannot substitute for those commands. Choose and document the disable BUSY/timing policy and pulse duration: native selected route uses 1 microsecond while m1n1 uses 10 microseconds. Before hardware, qualify actual C against nonlatched, write-only/self-clearing command bits, committed-but-error writes, forced release writes, and cleanup uncertainty. The existing 98 checked-API cases assume latched readback and do not cover this hypothesis.

Still missing: live native wrapper/BUSY policy applicability; any actual RESET31 assertion result; reset coverage; cessation of GPU/ASC accesses; fresh firmware/DATA and restart contracts. Successful command delivery alone does not authorize unmap, free, reset/restart retries, or warm START/INIT. The current built-in driver cannot be live replaced, and the consumed owner gate cannot attempt this candidate. No new replay framework or driver implementation was started for this evidence freeze.
