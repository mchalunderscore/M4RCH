# First-NOP diagnostic and startup observation — 2026-10-09

Boot22eeabd2-a404-4c7e-958d-dffc56ad44d5; kernel7.1.13-m4rch-gpu-contract. Trial moduleSHA256 c1eaca609408945195d64cf426ca447919bc33b29e0c9f69d3cffa764e21ecbf. User reports everything normal after trial.

The integrated candidate removed the first NOP0 dependency bitmap on both queues, changing exactly two backing bytes. Native timestamp1 TA/3D work, shared context, ring selector1 and fragment hold254/release remained unchanged. This was an explicit diagnostic departure from the native NOP producer, not a proposed permanent format change.

Firmware consumed TA control producer2, fragment3 and root control32. Installed queues/context remained accepted. Native fragment release again cleared page51+0x347 bit6. Kicks4, pending flags3/3 and pending mask3. Target and completion changed zero bytes. All six live fault-info/address snapshots were zero. Pause request/ack1/1 became0/0. These observations do not establish GPU ring fetch, translation, shader execution or rendering.

Post-stop banked observation reproduced the prior configuration exactly: queue0 ring12810010000cc001, queue1 ring22810010000d4001; both21010=4000000000000,21020=ffffffffff,211e0=3fffffffffffff. Global210e8/f0/f8=0 and21100=4000000000000000. The initial-dependency explanation is weakened; do not repeat a counter/dependency-only variant without new evidence.

## Additional same-boot startup read

Extended normally unloadable observer was compiled with LLVM/W=1 against the running kernel. It verified ASC stopped, with GFX power held externally by retained asc_graph_init. Bank selector0/1 was restored to original1 and read back. No kick/reset/resume writes. Observer unloaded normally.

Startup211c0=11, matching native startup ad48/ad54/adc8 low7 replacement with11. This contradicts the narrow hypothesis that this startup setting is absent; it does not verify all engine initialization.

Banked21028 reads were5a865b0451 on queue0 andd0a088481 on queue1. Their meaning is unresolved: firmware1accc..1ad40 and32a30..32a58 condition interpretation of21028 on ring-config bit63, which is clear on both installed configurations. Do not label these values completed timestamps or compare them directly with timestamp1. Investigate the native conditions that change bit63 and associated scheduler transitions before attempting a bit override.

The matched host configureHardware method atfffffe00089dad38 computes geometry from queue+1c and derives the register word; its enabled-mask writes agree with observed hardware mask3. Firmware event-mask writes21108/21110 at27c80/27c98 and289c0/289d8 are not independently evidence of a missing startup register. Our fixture's other zero hardware fields remain unqualified.

## Next work

Trace hardware ring bit63 transitions, firmware pending-service dispatch, and the native queue geometry producer together. Correlate these with captured firmware DATA and root hardware defaults to find an evidence-backed integrated correction. No new submission candidate is prepared by this result. The existing main trial retains its backing/GFX power until reboot; do not force unload or warm INIT. No kernel/default-entry changes were made.

Raw artifacts: out/owned-first-nop-ready/live-candidate/asc-graph-init/boot-22eeabd2-a404-4c7e-958d-dffc56ad44d5; result-22eeabd2; poststop-observer; startup-observer. Private implementation-derived research, not clean-room. No private binary or full firmware TEXT should be exported.
