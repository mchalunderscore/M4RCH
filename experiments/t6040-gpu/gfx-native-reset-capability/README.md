# Distinct retained-owner native command probe

This offline API patch kit adds `apple_pmgr_t6040_gfx_native_probe()` to the qualified checked-reset driver. It does not change either existing API or the checked core. It is not a loadable hardware helper; the new built-in export requires a separately built/qualified kernel (`7.1.13-m4rch-gpu-native-reset`). No installation, hardware attempt, reset coverage, DMA retirement, backing release or firmware restart is part of this kit.

The starting PMGR source SHA256 is `93df185e68c3e69d428460db7fc725b85ed191f75d24753a0563536a0dd1da61`, and the public-header SHA256 is `22392cd82cfdabcc1796166612bbb1d7b935cc34111bc1bf930e72d8e328c71e`. They are read from `out/gfx-reset-kernel/linux`. `gfx-native-reset-observation.patch` applies additively to that tree. The mirrored full C/header describe the result, not replacement files to copy onto the current running kernel.

## Command sequence and qualification

The matching native lead is recorded in `docs/evidence/2026-10-09-gfx-reset-native-disable-semantics.md/.json`. This implementation borrows preserved command images and explicit combined assertion/release. It deliberately differs from Apple `_setPSLevel` AUTO handling and conditional T6041 retention/AXI-to-AF workarounds, whose GFX applicability has not been qualified. It also deliberately requires a minimum 1us delay **and** a bounded BUSY-clear check after disable, while Apple selects BUSY or a delay by an unqualified object policy. It is an experimental Linux command probe, not byte-for-byte native equivalence.

The exact existing machine/provider getter is reused, including its device reference/lock. The reset-controller mutex refuses every existing reset-core reference and blocks new references; the existing domain spinlock covers the sequence. The caller must retain its GFX runtime-PM ownership and retained no-work backing, serialize/seal the owner, and enforce one attempt. The API does not allocate, unmap/free backing, retire mappings, submit work, or initiate firmware restart.

Before writes it requires powered domain ON and ACTUAL/TARGET active, with RESET/DEV_DISABLE/PS_RESET/BUSY clear. It preserves original AUTO and explicitly writes an inhibited image from BEFORE. It rechecks active/clear state, then defines `B` from the fresh AUTO-held read with historical bits 8/9 cleared. From this point it explicitly writes `B|DEV_DISABLE`, delays1us, and polls the compatible active/inhibited state plus RESET-clear and BUSY-clear, without requiring DEV_DISABLE to latch. It writes `B|DEV_DISABLE|RESET`, delays1us even when the write reports an error, and obtains only a diagnostic assertion read. Neither command bit is required to read set. It forcibly writes `B` for release, then requires that release write to succeed and observes compatible active/inhibited power plus RESET/DEV_DISABLE/BUSY/PS_RESET clear before attempting policy restoration. Restore may immediately gate ACTUAL under original AUTO, as permitted in the old API. Every poll uses at most101 reads/100us of delay.

Every command, including policy commands, is a full-word forced `regmap_write()`. No new command uses RMW or can be elided because readback already equals its desired word. An attempted disable also receives its minimum1us delay even if its write reports failure.

## Observation ABI

`apple_pmgr_gfx_native_observation.common` embeds the existing observation unchanged. Its valid bits remain **successful sample** bits, including the last successful sample of a timed-out poll; they are never acknowledgements. `desired[8]` contains complete 32-bit words, not masks or RMW values. `command_attempts` is set before each corresponding call, and `write_error` records that call's return. An error may have committed; a zero in an unattempted slot conveys no evidence.

Command order: INHIBIT, DISABLE, ASSERT, RELEASE, RESTORE, CLEANUP_INHIBIT, CLEANUP_RELEASE, CLEANUP_RESTORE. Read-stage order: BEFORE, AUTO_HELD, DISABLED, ASSERTED, RELEASED, FINAL, CLEANUP_RELEASE, CLEANUP_FINAL. The header publishes these eight-slot enums and counts. `read_attempts`, per-stage `read_count`, last bus `read_error`, and per-stage `poll_delay_us` provide provenance separate from common valid bits. A timeout has successful bus reads (`read_error=0`) but a nonzero overall operation/cleanup error and a bounded count/delay; it is not a read-bus failure.

Cleanup release and final reads share `common.cleanup_final`/VALID_CLEANUP_FINAL. If the final read fails, that common field retains an earlier successful cleanup-release sample. Consumers must use the per-stage read attempts/count/error to identify what was last observed. Failed reads do not overwrite successful receipt values with a provider's output buffer.

`release_command_verified` requires a successful forced release write and compatible clear-state reads. It does not confirm physical release of an unobservable line. `sequence_completed` indicates primary command delivery and final policy checks only. Neither flag establishes physical reset acknowledgement, GPU/ASC access cessation, or permission to release backing.

## Errors and cleanup

All failures after the first attempted inhibition enter cleanup. The preserved pre-inhibit clear image is the fallback if no fresh held read could be qualified. Cleanup forcibly writes this AUTO-inhibited image for inhibition and again for release, regardless of prior bus errors. A release write error is recorded and sampled only for diagnostics; a successful-looking read after that error cannot authorize AUTO restoration. A successful release write must still pass the bounded compatible clear-state check. If release remains uncertain, no cleanup restore is attempted. Failed writes can defeat inhibition or release despite the intended image, so the receipt preserves uncertainty rather than claiming actual inhibition.

Only a successful release write/read check permits cleanup restoration. A subsequent restore error can have committed; the receipt reports this separately and does not claim policy restored just because a diagnostic read matches. The first primary and cleanup errors remain visible even if later cleanup recovers. There is no recursive retry or repeated reset assertion.

## Actual-C replay

Run the staged actual-core harness in a fresh output directory:

```
python experiments/t6040-gpu/gfx-native-reset-capability/test-gfx-native-reset-api.py \
  out/gfx-native-reset-api/staged/pmgr-pwrstate.c \
  out/gfx-native-reset-api/validation-new
```

This reuses the checked API's small extracted-C fault-harness method, rather than introducing a new framework. The runner asserts that removing the two additive driver blocks and appended header ABI exactly reproduces every byte of the qualified v1 inputs. It compiles the new actual core with ASan/UBSan. The independent model covers all nine combinations of separately latched, nonlatched-readback, and self-clearing bit10/bit31; both AUTO policies; every primary read/write site; prewrite refusals; persistent bus failure; committed-error writes; cleanup write failure/uncertainty; preservation of stale successful receipt values; power/policy changes; and bounded status timeouts. Explicit combined assertion, forced release even when raw command bits already read clear, minimum delays after uncertain assertion, lock balance and AUTO restore ordering are asserted.

The current396 cases are CPU-only. Device-tree/provider checks, real locking races, regmap/MMIO behavior, BUSY semantics, native wrapper policy, reset scope and physical DMA/access cessation remain excluded. Independent kernel-object W=1 compilation and separately qualified kernel construction are recorded by the kernel preparer; no hardware inference follows from build or replay success.

Independent source/ABI review and a second396-case ASan/UBSan replay passed with matching C/core/header hashes. The source and additive patch are frozen. Each poll has at most100us of deliberate delay; a path with four primary and two cleanup polls can accumulate up to600us plus the two minimum delays. This is a software delay bound, not a hardware wall-time guarantee. The harness delay bound covers its injected models only and is not a universal core elapsed-time bound.
