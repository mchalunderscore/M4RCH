# Native T6040 Gravity component v3

This batch extends the existing Gravity `Platform::hwdata` and `FirmwareSpace`
producers. It contains native MCC, CAXI, MTR and inherited counter geometry,
canonical absent slot27 flags, native descriptor flags for those four resources,
independently decoded performance rows for both
clusters, the matched root interface identifier, and native `no-gpc` policy.
It keeps normal startup disabled: native bundle, power, Region C, channel/root
bindings and work cursors still need implementation.

The source-evidence inputs are the frozen v1 constructor followup and numeric
reports in `out/gpu-gravity-normal-boot-v3-source-evidence`. Source span hashes
bind those reports to the matched private driver without publishing instruction
bytes. The counter maps its first page through the existing writable slot40
alias and adds its second page once. Native descriptor/PTE permission translation
remains incomplete; the mapping selections are recorded as experimental.
The native descriptor flags are produced separately through `CPU flags & 2`;
they do not establish Linux page write permission.

The offline qualifier compiles the actual component and actual `RootPointers`
serializer into a small Rust executable. It compares complete produced bytes
against independent numeric evidence and tests two-cluster voltage rows, input
rejection, native absent slot27, counter aliases, deduplicated mappings, GPC
selection, root identifier selection and callback error propagation. The root
serializer test supplies its pointer values explicitly; it does not qualify the
production root bindings.

Stage and qualify once in a fresh destination:

```sh
python3 experiments/t6040-gpu/desktop-integration/t6040-native-boot/stage_v3.py out/gpu-gravity-normal-boot-v3
python3 experiments/t6040-gpu/desktop-integration/t6040-native-boot/qualify_v3.py out/gpu-gravity-normal-boot-v3 out/gpu-gravity-normal-boot-v3/qualification-v1
```

The designated module build owner can then compile only this staged module
against the already prepared kernel:

```sh
sudo -n python3 experiments/t6040-gpu/desktop-integration/t6040-native-boot/build_module_v3.py out/gpu-gravity-normal-boot-v3
```

The builder saves make's actual return status before postchecks. Generated
`.mod.c` files are excluded from immutable source pins. It records the linked
module and checks source/kernel immutability; it does not install or load the
module, rebuild the kernel, or perform GPU actions. Existing v1 and v2 stages
remain separate.
