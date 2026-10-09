# Live ring selector and hardware queue status — 2026-10-09

Boot0ae64504-a8ea-4785-93c0-1a702d3069f1, kernel7.1.13-m4rch-gpu-contract. Fresh qualification and combined ring-selector1 trial returned normally. Both firmware KSM rows contain header1, expected owned FW/GPU ring addresses, installed flags1, geometry10 and TA0/fragment1. Shared owner context and wrapped baseline remain accepted. Pointer control records complete to2; kicks counted4. Target and completion storage unchanged; no EHLC header or application response. User reports everything normal.

Post-stop read-only observer, with GFX confirmed on and trial consumer active, reads SGX21038=3,21040=0,211c8=0. Firmware uses21038/21040 as per-queue enabled masks, so hardware retains queue0/1 enable bits. This is stronger than merely observing firmware rows, but does not prove ring fetch or execution. Firmware pending queue flags remain3/3 and mask3, config-write-bypass0. Observer unloads normally, without queue-selector writes/kicks/reset/resume. Main trial context/backing stay pinned.

Numeric correction: prior selector report transcribed SGX201008; matched movk2-at16 addresses **SGX21008** (also21018,21038), inside mapped physical288020000 page. The firmware bit48 packing observation is unchanged. Its ASID interpretation remains inferred.

## Next integrated candidate

out/owned-zero-baseline/{prepared,live-candidate} restores initial config baseline0 and NOP predecessor0, preserving selector1, installed queues, shared context, native timestamp1 work and all shader/register/resource data. Exactly20 backing bytes differ: ten perqueue. The wrapped predecessor was a hypothesis; it may wait on a timeline the hardware never initialized. Zero is an alternative experimental starting state, not a proven correction.

The combined trial now takes bounded read-only KSM snapshots before-root, after-publication,1s,5s,15s and before-stop, while holding GFX power. No scheduler/reset/register writes added. Matching LLVM/W=1 build passed without warnings. Next fresh boot: qualify then run `run-root-envelope.py out/owned-zero-baseline/live-candidate --graph --run`; decode with analyze-owned-work.py. Do not warm-retry or force-unload this retained trial. No kernel/default-entry change. No rendering or accelerated desktop verified.

Raw evidence out/owned-ring-selector/live-candidate/asc-graph-init/boot-0ae64504-a8ea-4785-93c0-1a702d3069f1; result out/owned-ring-selector/result-0ae64504; independently built read-only observer/result out/owned-ring-selector/poststop-observer. Private implementation-derived, not clean-room.
