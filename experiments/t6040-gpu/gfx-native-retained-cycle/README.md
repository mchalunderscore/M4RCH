# Distinct native-ordered retained-cycle experiment

This family is prepared from frozen retained-cycle v6. It changes the second
START admission to fresh known6a or6c before the separate paired ON, after ON,
and immediately before the final fresh CTRL44 RMW. START clear, valid empty RX,
valid available TX, first successful own PWRGATE/strict physical OFF and fresh
same-consumer ACTIVE ownership remain mandatory. Unsupported status6e/48 or
invalid operands never permit START.

Selected source is `out/gfx-native-retained-cycle/prepared-owner-v1`. Actual C
qualification is `out/gfx-native-retained-cycle/owner-qualification-final-v1.json`
(115 ASan/UBSan cases). New state logging uses five complete phase-bearing
newline rows; the measured worst-case row is 422 bytes. The final compiled
candidate and Python receipts are a separate root handoff; this file alone does
not authorize loading a module.

Commands are `sample`, `gfx-snapshot`, one first `gfx-powergate` and one
`gfx-native-retained-cycle`. The second intent and PM/coordinator/transport
states remain independent of the first consumed epoch. All 174 page identities,
installed host root, joined context, consumer, mappings and module remain
retained on every result. An uncertain second result keeps its new reference
where ownership has transferred, without a compensating get/put or retry.

Known6c admission is a bounded native-order hypothesis motivated by the actual
v6 refusal and matched AppleA7IOP/V6 start bodies. The second sequence permits
one autonomous HELLO/map and management PWRGATE/OFF roundtrip; it adds no
INIT220, application endpoint/root publication, context reattach, queue reset,
DATA restore, rendering, DMA retirement or general restart capability.

The currently loaded v6 owner has consumed both intents and holds its second
reference after refusing before START. It must remain untouched. Only the root
operator performs new hardware actions from a fresh boot after final receipt
and preflight validation. Frozen v6 and every historical preparation/capture
remain preserved.
