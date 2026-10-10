# Selected Gravity Mesa full link, 2026-10-10

The full selected Mesa 26.3.0-devel Asahi Gallium/EGL/GBM stack compiled,
linked, and installed into `out/gpu-desktop-mesa-linked-v1/prefix`.
Ninja completed all 1136 steps. Two existing unused-variable warnings in
`agx_state.c` were the only compiler warnings. Nothing loaded or rendered.

The fresh full source copy differs from the preserved baseline only in the
two exact selected v2 metadata files, `agx_device.c` and `agx_g16_model.h`.
Before/after tree hashes confirm that the baseline source/build/prefix and
selected metadata stayed unchanged. The source, configuration, commands,
logs, artifact hashes and symlink targets are pinned in the adjacent JSON
and the workspace's `receipt.json`.

The private prefix contains `libgallium-26.3.0-devel.so`, `libEGL_mesa.so.0`,
`libgbm.so.1`, and `lib/gbm/dri_gbm.so`. EGL and GBM directly depend on this
private Gallium library; no per-driver DRI directory is installed. Only the
Asahi Gallium driver was configured. Meson used installed dependencies and
`--wrap-mode=nofallback`; Vulkan and software drivers were not selected.

The existing headless smoke harness also links. Its first link failed because
the new helper omitted the selected Asahi header search path. Adding that
path fixed the link without rebuilding Mesa. The original helper and failed
log are retained. The harness was never executed.

A later receipt correction restored the exact failed link command from the
immutable `failure.json`. The repair had accidentally added its include path
to that old argv list. The successful corrected command stays separate; the
erroneous ledgers and docs are preserved in `provenance-before-correction-v1`.
This correction ran no build, link, loader or ELF verification commands.

`elf-dependency-closure.json` statically resolves all dependencies across
28 ELF files with zero missing entries. It records system GLVND EGL/GLES
dispatch libraries and the private Mesa vendor stack. This uses `readelf`
and the system library cache; it does not prove an actual loaded identity.
`future-loader.env` records exact EGL vendor, GBM backend and private library
paths for a later owner-selected harness. It was never sourced. The built
no-op DRM shim is not part of that future loader environment.

Wayland protocols are absent locally, so this build exposes the prior
surfaceless/DRM EGL platforms. Wayland desktop integration remains a separate
dependency step. T6040 normal initialization and G16S graphics gates remain
closed. This result is build preparation and does not add a v16 trial gate.

Reproduce into a fresh workspace, using existing dependencies:

```sh
python3 experiments/t6040-gpu/desktop-integration/build_mesa_linked.py out/gpu-desktop-mesa-linked-REPLAY --jobs 8
python3 experiments/t6040-gpu/desktop-integration/finalize_mesa_linked.py out/gpu-desktop-mesa-linked-REPLAY
```
