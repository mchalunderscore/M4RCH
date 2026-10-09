# Live shared scheduler context and baseline — 2026-10-09

Boot47a5225e-cec8-4625-ba52-39be7602b9c2, kernel7.1.13-m4rch-gpu-contract. The combined scheduler-start candidate module2c35a0f8eccc2193b7de73390170d3fc299c5c3cd1096bf47589d6e946669971 passed fresh qualification and returned normally. User reports desktop, built-in input, USB and networking normal.

Both KSM queues remain installed with expected FW/GPU ring addresses and TA0/fragment1 identities. Both firmware baseline entries now contain40-bit wrapped predecessorffffffffff. Both firmware owner-context pointers13bf88/13bf90 point to the shared owned contextfffffc2000b18200. Firmware initialized nine bytes in that context, including queue-membership bits for queues0/1. These captures verify association/initialization of the supplied owner-context object, not its connection to the hardware UAT ASID.

Config/add-kicks pointers consumed to2 on both queues; four kicks counted. Neither target nor completion/SPM storage changed. No EHLC header or application mailbox response during30seconds. AP-quiesce/IOP-sleep ACKs and ASCstop readback pass; context/backing remain pinned until reboot. No GPU fetch, shader execution or pixels verified.

## Next candidate: align ring header with owned UAT slot

The matched firmware loads config4 into w22 at19214, then packs it into the GPU ring configuration at bit48 (198a0..198c0). Current headerword0 is retained in both firmware rows; our owned UAT root is installed only in slot1. Bit48 packing matches native TTBR ASID encoding, suggesting the ring is selecting an empty translation slot. This is an inference, not independently verified hardware field semantics.

`out/owned-ring-selector/{prepared,live-candidate}` changes only config4 from0 to1 in each queue (two backing bytes), preserving accepted shared context/baselines, queues, actual work/register lists, shaders, target and aliases. Builder asserts exact matched firmware load/packing words. Matching W=1 build, artifact identity, byte-change checks, Python compile and diff checks pass. Header after capture should report1. No extra host SGX writes.

Next normal Linux reboot, fresh qualification and combined `run-root-envelope.py out/owned-ring-selector/live-candidate --graph --run`, then `analyze-owned-work.py`. No INIT-only repetition or force unload/warm retry; no kernel/default-entry changes. If no execution appears, distinguish hardware translation/fault status and initial GPU scheduler state from application command/context issues. Keep all hypotheses visible rather than claiming valid draw readiness.

Source experiments/t6040-gpu/prepare-owned-ring-selector.py. Exact result/capture in out/owned-scheduler-start/result-47a5225e and out/owned-scheduler-start/live-candidate/asc-graph-init/boot-47a5225e-cec8-4625-ba52-39be7602b9c2. Private implementation-derived, not clean-room.
