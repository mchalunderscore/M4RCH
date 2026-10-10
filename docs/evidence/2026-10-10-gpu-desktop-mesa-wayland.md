# Selected Gravity Mesa Wayland build, 2026-10-10

The full selected Mesa 26.3.0-devel Asahi Gallium/EGL/GBM stack now compiles,
links and installs privately with Wayland support. The prefix is
`out/gpu-desktop-mesa-wayland-v1/prefix`. The installed EGL vendor library
retains `libwayland-client.so.0`, and the build contains the compiled Wayland
platform, Linux dma-buf protocol and Wayland loader objects. Nothing loaded
or rendered.

The missing `wayland-protocols` dependency was built and installed into a
separate private prefix. Its official 1.41 archive matches the exact SHA-256
in the selected Mesa wrap. Mesa resolves those private protocol definitions
and the installed Wayland 1.26.0 client/server/backend packages. Only the
Asahi Gallium driver was selected; Vulkan and software drivers were not.

A user reboot interrupted the original Ninja build after 241 of 1146 steps.
The continuation preserved that incomplete log and command ledger, verified
the saved source and input trees, and finished the remaining 905 steps in
the existing build directory. The interrupted command has no invented exit
code. Its original in-memory receipt, invocation and initial environment
were unavailable; the reconstructed receipt labels that provenance gap.
The resumed compile, private install and headless-harness link all returned
zero. The only compiler warnings were the same two existing unused variables
in `agx_state.c`.

The first finalizer incorrectly required a server-library `DT_NEEDED` entry
in EGL. Meson includes that dependency in its link recipe, but `--as-needed`
drops the unused direct reference. The correction accepts the actual client
dependency and compiled Wayland objects. The failed finalizer and its logs
are preserved. Existing successful ELF inspection commands were reused;
this correction rebuilt nothing and repeated no `readelf` commands.

Static dependency resolution covers 29 ELF files and 105 edges with no
missing entries. It does not prove an actual loaded identity. The harness
remains linked only, and `future-loader.env` was never sourced. The built
no-op DRM shim is excluded from that loader recipe.

Before/after tree hashes preserve the original full source/build/prefix,
selected v2 metadata, previous linked Mesa prefix and protocol source.
The source still differs from the original baseline only in the two selected
metadata files. Configuration, logs, artifacts and failure history are
pinned in the adjacent JSON and the private receipt/freeze files.
T6040 normal initialization and G16S graphics support still require their
hardware integration work. This build adds no requirement to the prepared
v17 trial.

For a fresh private build:

```sh
python3 experiments/t6040-gpu/desktop-integration/build_mesa_wayland.py out/gpu-desktop-mesa-wayland-REPLAY --jobs 8 --protocols-archive out/gpu-desktop-mesa-wayland-v1/wayland-protocols-1.41.tar.xz
python3 experiments/t6040-gpu/desktop-integration/finalize_mesa_wayland.py out/gpu-desktop-mesa-wayland-REPLAY
```

`resume_mesa_wayland.py` is for an established interrupted build whose prior
compiler process has terminated. Do not use it to replace a live process or
rebuild this frozen result.
