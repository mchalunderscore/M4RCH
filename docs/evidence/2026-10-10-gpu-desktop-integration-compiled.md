# Desktop integration compiler checks

Selected v2 topology/profile changes compile as an isolated `asahi_m4.ko` against the existing native-reset kernel. The compile retained 15 Rust warnings (including deprecated `fetch_update` and unused code); it has no compiler errors. The frozen kernel sources/configuration and active desktop were not changed.

The patched Mesa `agx_device.c` also compiles cleanly using the saved actual Mesa compilation command, with its selected metadata header. It is a translation-unit check, not a full Mesa library link. Its source hashes match v2, so no unchanged compilation was repeated. The headless EGL/GBM harness linked, and six Rust tests, 5,194 metadata assertions and 22 acceptance-criteria assertions passed offline.

T6040 normal initialization and G16S scene/shader/firmware layout gates remain closed pending the hardware execution contract. No module was installed or loaded, the headless harness was not executed, and GPU rendering/presentation remain unproved. This prepares the normal-driver identity and validation path in parallel with the first draw.

[Compiler receipt](2026-10-10-gpu-desktop-integration-compiled.json) binds selected sources, actual commands, logs, object/module artifacts and the [v2 implementation handoff](2026-10-10-gpu-desktop-integration-v2.md).
