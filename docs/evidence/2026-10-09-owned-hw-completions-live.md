# Four hardware completion rings — live result 2026-10-09

Boot520da35a-487e-4575-97b3-af12afa2936c, kernel7.1.13-m4rch-gpu-contract. Candidate module d87f930cf070db5758f361f782d66494564193c467ba49ef7878c99ce80ee8be ran once and returned normally. User reports everything normal.

At1s/5s/15s/before-stop all four completion configurations match(64<<48)|deviceVA|1:400010000d8001,400010000dc001,400010000e0001,400010000e4001. All four status registers and ring byte-change counts were zero at those samples; post-return rings also unchanged. Firmware installed the new ring descriptors. This is real initialization evidence, not completion/execution/rendering evidence.

Target/completion unchanged live and post-return. Existing queue config/kicks/release accepted; pending flags3/3/mask3. All six live fault-info/address reads0/0; startup211c0=11, other sampled progress21048/50/58/60 zero. No new application messages/EHLC. Full decoded results in companion JSON and out/owned-hw-completions/result-520da35a; raw capture in live-candidate/asc-graph-init/boot-520da35a-487e-4575-97b3-af12afa2936c.

Native count investigation: host895c100 adds NOP count to descriptor2dc,895c14c increments for the main kick,897f1d4 increments by1. The opcode14 count is a natural command count in this producer, so firmware deferred1b088 count<<8 is not evidence that our initial add2 should become512. Avoid another counter-only variant without stronger evidence.

The recent experiments submit the full authored TA/3D pair, but filling startup prerequisites one at a time has produced too many incremental reboot rounds. Next consolidate remaining engine initialization, device/context mapping and work-fetch requirements from the native host plus exact firmware consumer paths, then construct one integrated and diagnosable candidate. No next submission candidate is prepared by this result; do not reboot merely to repeat the same trial. A useful fault or verified hardware work fetch/completion is the next milestone; no near-term triangle ETA is established.

Manual reboots are operator-controlled; they can be automated if the user asks. The technical reboot requirement remains: acknowledged firmware quiesce stops ASC but does not prove retirement of GPU queues, translations and DMA references; earlier warm INIT failed. Retain current asc_graph_init backing/GFX until a fresh boot. Never force unload or reuse freed mappings. A reliable reset/unload path remains unverified. Kernel/default entry unchanged.

Private implementation-derived research; exclude private binary/full firmware TEXT/disassembly from exports.
