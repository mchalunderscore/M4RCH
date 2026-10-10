# Gravity desktop integration staging

This kit adapts the existing Gravity Linux/Mesa stack using selected source
copies. It does not edit the frozen native-reset kernel or pinned Mesa tree.
The source pins are in `base-inputs.json`; the saved integration assessment is
`docs/evidence/2026-10-10-gpu-desktop-critical-path-stack.md`.

The Linux patch carries the selected profile through probe, DRM registration,
runtime and platform construction. A pure topology value separates logical
slots from enabled cores, preserves explicitly supplied masks, and supplies
GET_PARAMS identity instead of hardcoded T8132 values. T6040 metadata supports
two clusters with ten logical slots each; captured J614s masks `3db/3db` give
16 enabled cores. Absent masks never fall back to this capture. Revision still
comes from the actual ID register in the existing runtime.

Initialization has an explicit selector for the implemented T8132 builder.
Every constructor checks it before donor resource/build operations. T6040
normal startup remains disabled, even if someone changes only its metadata
flag. A real T6040 initialization implementation must replace the pending
power/initdata/application boundary; this patch does not authorize donor
firmware objects, MMIO or scene/shader layouts.

The Mesa patch validates chip, variant, die/cluster count, logical slots and all
enabled masks immediately after GET_PARAMS. It refuses malformed identity or
unqualified G16S before VM allocation. G16S render/compute gates stay closed;
this is not a hidden option to run unqualified G16G packets.

Reproduce in a new output directory from the repository root:

```sh
python3 experiments/t6040-gpu/desktop-integration/stage.py out/gpu-desktop-integration-replay-v1
python3 experiments/t6040-gpu/desktop-integration/qualify.py out/gpu-desktop-integration-replay-v1 out/gpu-desktop-integration-replay-v1/qualification-v1
```

The qualifier recompiles only the pure Rust profile, Mesa header tests,
synthetic CPU readback criteria and one small headless harness. It checks
patch replay, caller bindings and unchanged frozen inputs, exercises all 1023
valid one-cluster masks and masked G16S inputs, rejects crossed identities and
nonzero trailing masks, and compares the actual Rust/C J614s topology output.
C pure tests use ASan/UBSan. Full kernel/module and Mesa compilation remains a
separate integration check. Every qualification uses a new output directory;
failed results are preserved. The EGL harness is linked, never executed by the
qualifier, and these checks do not prove GPU execution.

`headless-smoke.c` is prepared for a future functioning T6040 DRM/Mesa stack.
It requires an explicit Asahi render-node fd, complete J614s GET_PARAMS
identity (including the saved B1 revision), a GBM-bound surfaceless GLES3
context and an Apple M4 Pro/G16S renderer. It rejects software rendering.
Two draws change the triangle from red to green over a blue background. Each
must complete a GL fence within five seconds and produce complete RGBA8
readback with correct interior/background pixels and reasonable coverage.
Native EGL fence export is tested when advertised and reported separately.
RGBA files and success JSON use exclusive creation and fsync; no existing
capture is overwritten. A userspace alarm does not guarantee that a wedged
kernel ioctl can be interrupted. A failed run is not permission to repeat it.

Only after normal startup and G16S graphics are qualified, a hardware owner
can manually run the linked harness with a new empty capture directory:

```sh
mkdir out/headless-smoke-FRESH-ID
timeout 35s out/gpu-desktop-integration-replay-v1/qualification-v1/headless-smoke /dev/dri/renderD128 out/headless-smoke-FRESH-ID
```

The node above is a placeholder: choose the actual verified Asahi node. Use
the reviewed private Mesa build through an explicitly selected loader/library
path; do not globally install it to try this harness. Pin that loaded Mesa and
kernel identity together with the captures. Success proves only those
headless submissions. It does not qualify kernel teardown, buffer import into
simpledrm/DCP, modifiers, scanout, the compositor, or desktop performance.

Next integration work is the native T6040 startup/power/initdata/application
contract, truthful multi-cluster boot input binding, G16S scene and Apple9
shader-entry/graphics layout support, and repeated EGL/GBM workloads. Desktop
presentation, KWin's QPainter overrides and DCP takeover remain separate.
