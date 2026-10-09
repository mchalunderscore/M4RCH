# Recheck of the supplied M4 Pro ABI reference

The current `/home/alice/Downloads/M4-PRO-GPU-HARDWARE-ABI.md` has SHA256
`2818ced00eea77f662be9339ee6dae717bd1330e2a46bc927e53190edf6b98db`, identical
to the October 7 reference recorded in `2026-10-07-gpu-abi-reference.json`.
It supplies no new bytes or new execution evidence.

Matched Apple25G83 / AGX353.14 analysis supersedes its separate queue-pointer
producer offset: `+0x40` is the host producer, `+0x50` the reset sentinel
`0xffffffff`, and `+0x60` capacity. This is the same record class, distinct
from the `0xc0` channel state and the accelerator's 24-byte submission ring.
See `2026-10-08-private-queue-pointer.md` and
`2026-10-08-private-channel-reset.md`. The live candidate already uses these
fields through `prepare-owned-work-publication.py`. The unused queue codec
in `g16s_abi.rs` is now corrected, with its existing test checking preservation
of every other byte. Its only non-test importer uses the voltage serializer;
this correction changes no hardware candidate or submission behavior.
The standalone Rust codec suite passes all 10 existing tests after correction.

The reference's J616s has 20 cores; this J614s has 16. Existing
`graph-register-batch.py` preserves masks `0x3db/0x3db`, packed `0xf6fdb`.
The native TA allocation stride is `0x9c0`, versus the document's stated
`0x9a0` record extent: these are not established as interchangeable meanings
(`2026-10-08-private-pool-sizes.json`). The integrated command pool reserves
64 slots of `0x2240`, with fragment in slot 0 and TA in slot 1. Current
preparation already handles the four fragment register lists at
`0xa0/0x7c0/0xee0/0x1600`, TA list at `0x60`, and packed completion metadata.

The owned triangle uses the Gravity Mesa draw path for three vertices,
one instance, a 64x64 RGBA8 target, native TA/fragment commands, and four
hardware-completion rings. Relevant evidence is
`2026-10-08-apple9-draw-preparation.json`,
`2026-10-09-owned-hw-completions.md` and its live report; installed rings and
consumed control records have not established execution or changed pixels.
The latest native-init recovery report records no completed recovery cycle
and no triangle submission. Compute save-state offsets in the attachment
are reference material for a later compute path; the current triangle uses
SKSM register lists. No new wake or hardware trial follows from this recheck.

The power assertion counter at Region C `+0xe51` was already identified by
`audit-firmware-interface.py`. This recheck traced its host publication:
native `submitDeviceControl` at `89a6924` indexes the classification table at
`712e084`. Class 1 calls virtual slot `aa0`, resolved to `89b7cf8`, which
increments the packed u32 counter and executes DMB ISH. Matched firmware
`3900..3924` compares it with `status_b+e438`, invokes `33a68` on mismatch,
and `5154..5164` increments the consumed counter for class 1 after dispatch.
The native and firmware classification tables match. Root refresh opcode
`0x16` has class 0, as already checked by `model-control-refresh.py`.
Both captured counters are zero in the latest idle-recovery trial. KSM work
opcodes 15/14/16 belong to a different namespace. This is a requirement for
future device-control expansion, not evidence for a missing assertion in the
current trial or a reason to try arbitrary counter increments.

The hardware `+0x26b8` pointer already references the owned `0xe40`-byte
counter allocation at `fffffc200012c000`. Profile A already has 11 rows with
two cluster columns and `0x40` stride. Profile B remains deliberately disabled
and zero because its source mapping is not qualified. No AON table constructor
is implemented. Native `populateAONPTDIdentifiers` at `89e92fc` corroborates
the `g0TR/g1TR/r0TR` identifiers, but the supplied document does not give the
destination, remaining record fields, enablement policy, or lifecycle needed
to use it. These are incomplete power-management features, with no established
connection to the phase-2 recovery stall. The current sensor fixture has zero
mask/count; the AON table and temperature sensor table must not be conflated.
