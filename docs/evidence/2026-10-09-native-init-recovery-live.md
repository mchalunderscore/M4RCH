# Native initialization recovery result and next diagnostic

Boot `c7292f21-ae68-4948-b694-e773a22946d0` ran
`out/native-init-recovery/resident-candidate`, module SHA256
`c76cb717a2b3a9a82a76abc9c73f33e47f9657019bc3ab2a77a40b693835a0ec`.
The first forced-host recovery reached phase 1/counter 1. After host phase 2,
phase 3 did not arrive within five seconds. No mailbox crash or EHLC record
was observed. Zero recovery cycles completed, resident mode was not entered,
and no triangle was submitted. The complete numeric result is in the adjacent
JSON file; its capture directory is recorded there.

The native initialization batch was present in owned memory: hardware
`f30..f3f = (0,1,1,0)`, engine masks `254c/2550/2554 = (3,7,7)`, and
`power+3b50 -> fffffc200014f000`, a retained, zero eight-byte temperature epoch.
New extrema stores after firmware `301a8` support progress beyond the earlier
null-pointer failure. The current failure is a stall after host acknowledgement,
not a repeat of the old null dereference.

Shutdown obtained AP QUIESCED ACK 1 but IOP SLEEP ACK 0. ASC control/status were
`0/0x6c`; stop readback was not verified. All 174 owned pages, joined context,
mappings, GFX ownership and a module reference remain pinned. All three USB PD
controllers remained bound. Do not wake, reload or force unload this instance.
A normal reboot is required before another candidate can be loaded.

## What the saved state narrows down

Owned power fields `+38`, `+78`, `+63c8` and `+652c` are all 1. In the matched
firmware these are consistent with entering the down transition and not yet
completing a second power-up. The leading hypothesis is inside the firmware's
`c8f0 -> cda0 -> 2bdac` power-down path. Its unbounded polls include:

| Firmware poll | Operand | Required condition |
| --- | --- | --- |
| `2becc`, also `2c0c4` | primary `5960`, u64 | low three bits zero |
| `2bfec` | primary `5978`, u64 | bit 1 set |
| `2c11c` | PRC `d4c004`, u32 | low five bits equal requested state |

No saved register values distinguish these waits. Cached task context does not
establish the live PC because firmware cache writeback was not proven. Do not
claim an exact stuck instruction. Native platform mode `hardware+f20 = 0` is
explicitly initialized by Apple and must not be changed merely to bypass a poll.

The host restart interval contains no identified missing mandatory reset/MMU
operation before phase 2. Its submitted-timestamp table is `main+274 -> shared_4`,
128 records of 16 bytes; all 2048 bytes are zero before and after this idle trial.
The assertion counters Region C `e51` and status `e438` also match at zero;
refresh `0x16` does not require an assertion. These findings do not establish
that the entire power constructor is complete.

## Prepared diagnostic, not a hardware result

`out/recovery-power-wait/candidate` retains the same native initialization and
immutable draw backing. Work roots remain empty during recovery. It samples
the owned phase/power markers and, only during phase 2 with nonzero power state,
the three exact poll operands above. It performs no selector or poll-register
writes. Samples occur at 100 ms and one-second intervals in the bounded wait,
at return, and through the typed sample command.

If recovery fails, the candidate preserves a powered diagnostic session instead
of immediately attempting shutdown. Only sample/stop is allowed; no recovery
retry or triangle publication is admitted. This lets us inspect the stalled
state without losing it to the previous shutdown sequence. All memory remains
pinned. If both cycles succeed and consume fresh controls, the same instance
allows further idle recovery checks and one prepared triangle submission.

The module builds with `W=1`. Source/artifact receipts and wrapper interruption
quarantine are checked offline; there is no live result for this candidate yet.
See `2026-10-09-recovery-power-wait-candidate.json` for exact hashes. Repeatable
recovery, safe DMA retirement, GPU execution and rendered pixels remain unproven.
