# V24: full native power initialization and one cold triangle submission

This is a distinct experimental trial built from the retained v23 native triangle
payloads. It joins the byte-qualified native power/HW-power/Region C/AON writer,
fresh performance-map snapshot and architectural clock provider, and owned
backing for the native HW timestamp pointer. It does not repeat the failed
postdraw wake sequence.

Current boot 14343c22-f598-4eae-974a-b0edf7009530 is consumed. Do not load,
unload, sample GPU registers/RAM, replay, wake, or free its retained owners.
A user reboot is requested only after root selects a concrete READY bundle.

Root selected the candidate **READY for one future fresh-boot trial**. See
`docs/evidence/2026-10-11-native-full-power-v24-ready.json` and
`out/gfx-native-full-power-trial-v24/READY.json` for the exact candidate and commands.
A manual reboot is now required before any GPU operation.

The frozen V8 module built with zero warnings/errors. Its actual C/Rust ABI
matches the native fixtures. Root checked 98 build pins, six preserved triangle
inputs and 34 final qualification/closure pins. Launcher admission passed 103
cases; OFF capture passed 12 cases and four intercepted flows, including loss
of capture integrity after writing. The exact 39,884-byte initialized CPU-owned
snapshot is captured before root publication. No GPU trial has run yet.

## Experimental hypotheses

Full power construction may remove the firmware execution/control stall observed
with the old incomplete power image. Both native profiles and per-cluster voltage
providers are constructed from the selected raw ADT and fresh register maps.
The 20 W maximum is explicit Linux policy rather than a recovered Apple fuse.

Apple's native timebase is 24 MHz. Saved Linux uses a 1 GHz physical counter.
The trial scales the absolute standard physical counter to 24 MHz and logs the
raw counter/frequency. Equivalence to Apple's custom per-CPU counter offsets is
unproved. It never reads Apple's custom CPU register.

Native HW +0x28 points to owned RAM at 0xfffffc2181400000. The trial owns one
16 KiB backing page and an additional L2 table, for 176 total retained pages.
The full 64 MiB timestamp aperture is not backed. Confinement of all first-job
firmware accesses to this page is an explicit experimental assumption. Existing
Work, stamp, notifier, shader and render payload addresses remain unchanged.

## Intended launch and result

One future fresh boot performs admission, PM/coordinate ON, one performance-map
and clock snapshot, one ASC management boot, complete power construction before
root publication, native TA/3D submission, draw capture, then bounded OFF only.
No ON/START/rejoin/replay follows the retirement attempt. Ambiguous shutdown
retains the module, mappings, context and all backing. A rendered image and
qualified physical OFF are separate outcomes; neither is proved offline.

Build receipts and qualification outputs live under
`out/gfx-native-full-power-trial-v24`; durable numeric evidence lives under
`docs/evidence/2026-10-11-native-*v24*.json`. No kernel or GRUB changes are needed
for the module-only candidate. DCP integration follows GPU execution and
teardown evidence; this trial is not a GPU accelerated desktop.
