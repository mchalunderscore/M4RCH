# V24: full native power initialization and one cold triangle submission

This is a distinct experimental trial built from the retained v23 native triangle
payloads. It joins the byte-qualified native power/HW-power/Region C/AON writer,
fresh performance-map snapshot and architectural clock provider, and owned
backing for the native HW timestamp pointer. It does not repeat the failed
postdraw wake sequence.

Current boot29800a86-c89b-4072-b121-c40e264982dc is consumed. The v13
trial completed its15second submission/observation pipeline; firmware accepted
both work queues but no pixels changed. Idle-policy command was processed, then
bounded shutdown used NMI after no202ACK. CPU stopped, Fender disabled,
coordinateOFF/PMput completed; physical status0f000b00/domainOFF still had BUSY11.
All176backing owners remain retained. No rebootless restart or rendering claim.

Earlier v11Python and v12C admission omitted the new read-only telemetry leaves.
Both refused before GPU start; the C shadow released unpublished allocations.
These were repaired on the same boot in v13 before the actual cold trial.

READY is false. Per user direction, next work integrates known native scheduler,
event/completion and teardown/boot gaps into the Gravity caller, using the Apple
driver to resolve assumptions before another whole hardware trial. No new
individual hardware test or manual reboot is requested while that work runs.

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
