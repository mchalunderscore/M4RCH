# Auxiliary clock restoration: startup progressed to telemetry fault

Boot `0140aa26-6f9e-40f2-beb1-ff2cf3bfd59f` ran the reviewed candidate
`out/gpc-aux-recovery/candidate` once, module SHA256
`399e92e2b25fcafd3aa4ca7214bce65e41398310c8772f7c030311a7f6a5cf5e`.
Before loading, the previous GPU module was absent and all three USB PD
controllers and role providers were bound.

Restoring native CS/AFR tables and the timer page changed the outcome:
`power+38` and `power+78` reached 1 and all four hardware completion rings were
configured. The crash stack passes the main engine-on wait and reaches its
telemetry reporting callback. This is more evidence than the preceding
GPC-enabled trial's zero software power fields and stalled startup.

Firmware then faulted at PC `25674`, FAR `f98`, ESR `96000044`. The instruction
stores through cached slot9 VA `18f590`, which the captured DATA shows is zero.
Selector `10f98` becomes offset `f98`; the native callback writes the low and
high halves of `2000000000000001` at offsets `f98` and `f9c`.
Apple's matching constructor identifies this slot as PushTelemetryDashboard,
PA `5003d0000`, extent `4000`. Actual firmware instructions in emulator RAM
reproduce the null fault and complete both stores with the proposed mapping.
The native producer, firmware mapping consumer, crash registers and narrow
continuation review are bound in `2026-10-09-native-telemetry-slot9-crash.json`.

Initial controls remained `0/0/32`; all twelve work roots remained empty.
The module skipped recovery after the crash notification, so no recovery packet
or triangle was submitted and no recovery poll samples exist for this attempt.
No GPU execution or completed recovery is established.

The runner requested shutdown: AP QUIESCED and SLEEP were not acknowledged;
ASC final control/status was `0/4e` with stop readback true. This does not prove
DMA retirement. Both resident and diagnostic session flags are false; the
main module, joined context, mappings and all 174 owned pages remain pinned.
Do not use the resident command interface, repeat INIT, or force unload.

The complete saved capture is under
`out/gpc-aux-recovery/candidate/asc-graph-init/boot-0140aa26-6f9e-40f2-beb1-ff2cf3bfd59f`.
Its owned state and hashes are in the adjacent JSON. The next prepared candidate
is described in `2026-10-09-gpc-telemetry-recovery-candidate.md`.
