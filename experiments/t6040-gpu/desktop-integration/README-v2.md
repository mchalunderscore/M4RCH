# Selected integration stage v2

Use this version for the next isolated module compile. V1's pure checks passed,
but the actual module compile found a stale probe diagnostic referencing
`platform.core_mask`. V2 reads `platform.topology.core_masks[0]` instead and
adds a source check for obsolete singular core-mask member access throughout
the five changed caller files. No firmware/graphics execution gate changes.
V1 sources, patches, qualifications and compile failure are retained.

Reproduce and qualify selected v2 copies in new output directories:

```sh
python3 experiments/t6040-gpu/desktop-integration/stage_v2.py out/gpu-desktop-integration-v2-replay
python3 experiments/t6040-gpu/desktop-integration/qualify_v2.py out/gpu-desktop-integration-v2-replay out/gpu-desktop-integration-v2-replay/qualification-v1
```

The Linux patch is `gravity-linux-g16-topology-binding-v2.patch`; the unchanged
Mesa patch is `gravity-mesa-g16-device-metadata.patch`. Full normal-module and
Mesa compilation is still a separate check; pure tests cannot replace it.
The original README describes the implementation, headless harness and
remaining ABI gates. Its v1 staging commands are historical.

The headless harness remains linked only. Do not run it until the actual
T6040 initialization and G16S graphics path exist and the hardware owner has
selected the loaded kernel/Mesa identity and an explicit render node. This
version changes no baseline source, hardware, system desktop or boot settings.
