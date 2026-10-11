# V24: full native power initialization and one cold triangle submission

This is a distinct experimental trial built from the retained v23 native triangle
payloads. It joins the byte-qualified native power/HW-power/Region C/AON writer,
fresh performance-map snapshot and architectural clock provider, and owned
backing for the native HW timestamp pointer. It does not repeat the failed
postdraw wake sequence.

Current boot af201416-45d8-47ab-937d-7177942b2248 is consumed. Do not load,
unload, sample GPU registers/RAM, replay, wake, or free its retained owners.
A user reboot is requested only after root selects a concrete READY bundle.

The v8 trial refused before control due to a174/176 host owner count mismatch.
The v9 correction passed that guard, then firmware faulted at PC25698, FAR2b40
through missing telemetry read slot10 before publishing control or draw. Neither
trial rendered or attempted OFF. All176 owners and PM remain retained.

The v10 correction adds Apple's exact slot10 physical region and16KiB extent.
Actual saved-firmware replay reproduces the null read then succeeds with ordinary
RAM mapping; the exact qualified power writer preserves the new descriptor.
The v11 module also adds the native slot14 conditional fallback mapping. Both
descriptors survive the qualified power writer. Root selected candidate-v11
READY for one fresh-boot trial; a manual reboot is now required. See READY.json and durable live/replay evidence for current
status; older build/READY receipts are historical.

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
