# Prioritize first GPU execution and desktop integration

The user requested a faster route to a GPU accelerated desktop on 2026-10-10. Management teardown and restart experiments have consumed too much of the critical path. The immediate hardware milestone is a completed draw from a clean cold start with coherent pixel readback. The next boot should test a consolidated rendering candidate, with initialization, fresh control consumption, one submission and useful diagnostics in one owner. The preserved v12 management-only candidate remains ready but is no longer the recommended next trial.

The fixed two-restart limit is our software design. A generic numbered-cycle state machine can allow many successful cycles, with fresh evidence and one reference per cycle, while preserving original identities and stopping after uncertainty. It need not be completed before the first draw. A desktop primarily requires repeated completed submissions while the GPU remains on.

The current experimental execution path requires four successful recovery cycles before submission. Current class86 recovery fails before drawing, so this gate blocks the newer native initialization from being tested with the existing TA/3D job. A distinct clean cold-render profile should omit initial class86 and host recovery-phase forcing, and replace recovery-count prerequisites with fresh owned cold readiness. This does not clear failed history in the current loaded owner. See the [source-pinned cold-render specification](2026-10-10-gpu-desktop-critical-path-cold-render.md).

The shortest useful sequence is:

1. Cold start with the accumulated native initialization fixes, original mappings/context and healthy receive service. Keep work empty.
2. Automatically publish the existing operand-free control once and observe its own new read/prefetch advancement. Recheck owned reference, identities and idle immediately before work.
3. Publish the preserved TA/3D pair once, then capture actual hardware progress/faults, completion and coherent target pixels. A firmware ACK or consumed work cursor alone is not execution proof.
4. Adapt that proven contract into Gravity's existing DRM backend and qualify Mesa G16S, starting the source work in parallel. Demonstrate repeated headless EGL/GBM frames and synchronization.
5. Connect one viable display/compositor presentation route. Existing simpledrm supports the current software desktop; a GPU-rendered copy-backed bridge is an untested option. Native DCP work can proceed separately from first headless rendering.

The [existing-stack roadmap](2026-10-10-gpu-desktop-critical-path-stack.md) identifies the real integration gaps: T6040 normal startup refusal, donor G16G/one-cluster parameters and builders, Mesa's G16S rejection, and presentation/device selection. Reuse Gravity's buffers, VM, queues, submission and fences rather than inventing another desktop API. Merely removing rejection checks does not supply correct T6040 hardware behavior. The private Apple driver and matched firmware remain references for the hardware contract.

Change the workflow: batch mutually supported initialization changes into one diagnosable candidate; automate evidence capture and unchanged checks; use subagents in parallel on execution, DRM/Mesa integration and presentation. Measure progress by GPU completions, pixels, repeated frames and an accelerated application/compositor. Defer unrestricted management loops, retained app rejoin, full unload/backing retirement, suspend/resume and power tuning as prerequisites. Keep backing retained through the first render trial, and stop further controls on an uncertain outcome.

Current boot 911a still has the consumed, pinned v11 owner. No hardware controls were issued during this reassessment. The new cold-render candidate is a specification, not an implemented, built or qualified module. One fresh boot remains necessary to replace the current loaded owner. Preparing the direct execution trial first avoids spending that boot solely on additional management-only epochs. Existing frozen v11/v12 sources, builds and evidence remain unchanged.
