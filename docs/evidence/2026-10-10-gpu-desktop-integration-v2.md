# Selected Gravity integration: v2 correction

Use the [v2 kit instructions](/home/alice/Desktop/m4rch/experiments/t6040-gpu/desktop-integration/README-v2.md) and [selected v2 receipt](/home/alice/Desktop/m4rch/out/gpu-desktop-integration-v2/selected-source-receipt.json).

The actual isolated module compile caught a v1 probe diagnostic still reading the removed `platform.core_mask` member. V2 reads `platform.topology.core_masks[0]` and checks every changed caller for stale singular-mask access. V1 source, patches, pure results and compiler failure remain preserved.

[Selected v2 offline qualification](/home/alice/Desktop/m4rch/out/gpu-desktop-integration-v2/qualification-v1/qualification.json) passed six Rust tests, 5,194 Mesa topology assertions and 22 synthetic pixel/renderer checks, with 31 input pins and exact fresh patch replay. The headless harness links but was not executed. Frozen baseline sources still match their hashes. Parent has the v2 sources for another targeted module compile; that pending result is not claimed here.

The implementation otherwise matches the [original handoff](/home/alice/Desktop/m4rch/docs/evidence/2026-10-10-gpu-desktop-integration-v1.md): selected-profile initialization binding, explicit topology and truthful GET_PARAMS, Mesa validation and G16S refusal before VM creation, and a future headless GBM/EGL smoke harness. T6040 startup and G16S packet execution remain closed until their real firmware/application/scene/shader contracts are implemented. Hardware rendering and desktop presentation remain unqualified.

No baseline source, hardware, system desktop or boot settings were changed. This correction built only the small offline pure components/harness; no full kernel or Mesa build was run by the staging owner.
