# GPC policy correction and live recovery results

The native GPC initializer was missing from the experimental graph. Apple and
Gravity enable `hardware+ea0` by default when `no-gpc` is absent, as it is in
this board's captured ADT. Firmware copies this word to `18fc78`; zero skips
physical GPC startup while recording software power fields as 1. The independent
native policy and parser evidence is in `2026-10-09-native-gpc-policy.json`.

This corrects the earlier claim that `hardware+f20` supplied that gate. It maps
to `18fcc8`, and its native zero value remains unchanged. This correction changes
the interpretation of the earlier power fields; it does not alter captured data.

## Diagnostic trial before GPC restoration

Boot `cc72a5d0-97a0-40f6-9092-f7dffd23e177` ran
`out/recovery-power-wait/phase-aware-candidate`, module SHA256
`e6a7b0c26ef6d262c4c0a2414878cbac19a1f03a8d573c843b23e76d788eacb8`.
Initial controls reached 32/32/32. Recovery reached phase 1, then remained in
phase 2 after the host acknowledgement. Six sequential poll samples over the
five-second wait showed primary `5960=0`, `5978=1`, and PRC `d4c004=0`.
`5978` bit 1, the down acknowledgement, never appeared in these samples.
Owned fields `38/78/63c8/652c` were all 1.

The module retained ASC/GFX and sealed its diagnostic interface. A later typed
sample at monotonic 318.958 seconds still showed the same state and registers,
without sending another recovery request. No cycle completed and no triangle
was submitted. The user then rebooted normally.

The sampler was corrected before this trial to remain active throughout phase 2:
firmware clears `power+38` before the second `5960` and PRC waits. `power+78` is
the old state until the transition returns, not the requested down target of 0.

## GPC-enabled startup trial

Boot `706d9e50-c897-4479-8587-f19835a40166` ran
`out/gpc-recovery/candidate`, module SHA256
`246de548859b7b70fbdd762cedc32d3947524e1b4b2ffe11c3f0e038202aa220`.
The graph differs from the previous diagnostic by exactly one byte: the low
byte of `hardware+ea0` changes from 0 to 1. The native masks, temperature epoch,
control fixture, immutable draw and all mapping/lifetime rules are preserved.
The candidate passed its `W=1` build and full artifact/source receipt checks.

This time initial control read/prefetch remained 0 with producer 32. Recovery
was never requested: the control prerequisite timed out first. Counter/phase/
request remained zero; power `38/78/63c8/652c` also remained zero. No mailbox
crash was observed. The module retained a sealed diagnostic session.

A separate fixed read-only helper sampled the exact startup and main-transition
poll operands on this same boot. At monotonic 379.602 seconds:

| Operand | Value |
| --- | --- |
| ASC control/status | `0x10 / 0x6c` |
| Primary `5960 / 5970 / 5978` | `0 / 0 / 0` |
| PRC `d4c000 / d4c004` | `0 / 0` |
| Event-status operand `d44070` | `0` |

The helper verified the machine and ASC START, while its caller verified the
resident module's build ID, exact receipt, boot and retained diagnostic state.
It performed no command/selector writes and unloaded normally afterward. Its
module SHA256 is `dd5f8bae67e1627dcdb187339e0e9c5136c13dca3d5d1e04d39fdc9ff5eab2ab`.
The main GPU module, GFX domain, context, mappings and 174 pages remain retained.

`5970` low three bits being clear does not establish that its poll was reached.
PRC `+0` serves the auxiliary transition in `32248`; PRC `+4` serves the main
transition in `2bdac`. The auxiliary target is clamped by configured bounds and
cannot be inferred from `power+78=0`. Subsequent tracing binds the candidate's
zero bounds to `hardware+1b90/1b94`; they clamp the requested auxiliary state to
zero, which allows a no-change return without writing PRC `d4c000`.

The subsequent main transition waits for `d44070 & 0xffff == 3`. Its mask comes
from the chip-ID cluster count, not the newly added engine masks at `254c`.
Firmware writes the same mask back after observing it, so a pending-event
acknowledgement is plausible; this is not proof of a simple powered-state bit.
The exact live PC remains unproved, but this is the strongest unsatisfied sampled
predicate. The full bounds, mask and timestamp pointer chains are recorded in
`2026-10-09-gpc-startup-path.json`.

The native auxiliary blocks are independent CS and AFR clock tables from
`cs-perf-states` and `afr-perf-states`, not the main GPU profile-B voltage table.
Their eight-state ADT tables were omitted from this fixture. See
`2026-10-09-native-aux-power.json` and the following prepared candidate report.

Both captures and the isolated retained sample are summarized by
`analyze-recovery.py`, which binds the graph and normalized firmware identities.
It handles kernel log rotation using a unique 32-line retained boundary, so
earlier operations are not attributed to a later sample. The older capture
without register instrumentation correctly reports no MMIO observations.
Raw capture paths, log/input hashes and complete numeric results are in the
adjacent JSON. Repeatable recovery, DMA retirement and rendering remain unproven.
