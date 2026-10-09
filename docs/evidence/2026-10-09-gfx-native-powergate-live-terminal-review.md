# Independent native PWRGATE terminal review — boot d841b8bf

The single combined `gfx-powergate` operation returned `-16` before publishing
the management request. The terminal intent is consumed and sealed. No ACK was
observed, no RX frame was removed, no CPU-control write occurred, no paired OFF
was delegated and no PM put occurred. All 174 pages, mappings, context, consumer
and module remain retained. Only `sample` and `gfx-snapshot` remain admitted.

The final record at kernel time 359.198533 has `control_before=0x10` with
`request_attempted=0`, `ack_polls=0`, `rx_messages=0`, `clear10_attempted=0`,
`clear20_attempted=0`, `cpu_stopped=0`, `off_delegated=0` and `held=1`.
The printed request `0x60000000000202` is the configured request constant;
it is not a wire publication. Likewise, the phase name `cpu-stop-return` records
the propagated admission failure; its zero counters establish no CPU stop.

Reaching the assignment of `control_before=0x10` proves that earlier backing,
receive-journal, PM-accounting, recovery-state, idle-record and control-cursor
checks passed. In the exact pinned source, the remaining `-EBUSY` alternatives
are STATUS48 reading all ones, RX114 reading all ones, RXEMPTY being clear or
TX110 bit16 being set. This capture records no entry values for STATUS48,
RX114 or TX110, so it cannot identify which alternative fired. A pending RX
frame is plausible, but not established. No stale frame was decoded.

The admitted later diagnostic returned successfully at time 425.331375:
PMGR `0x1f0003ff`, ACTUAL/TARGET 15, BUSY clear, runtime active with usage1 and
held1, CTRL44 `0x10`, STATUS48 `0x4e`, and no PM attempt. These are later values;
they do not prove the validity or emptiness of the unrecorded admission reads.
The baseline and later logged power fields progressed 4119→14722 over
88.356453 seconds. Saved object bytes at `0x3652c` progressed 6786→14722 from
the terminal capture to the later diagnostic; separate owned bytes at `0x3e52c`
progressed 6787→14723. This establishes changing retained bytes, not qualified
producer identity or global cessation. Captures are non-atomic.

Cold, baseline, terminal and later capture hashes and complete extents verify.
All 56 render backing pages match the prepared fixture; all 35 job-pool pages
match the cold capture. All 12 work-channel cursor triplets remain zero,
deferred work rings match their fixture and control stays 32/32/32. The decoded
receive journal exactly matches its raw binary and stays unchanged at 50,410
records, with status flags0 and doorbells0. No work or triangle was published.

The old boot94cb trial reached paired PMP/PMC OFF and a successful normal PM
put, then failed its strict physical-OFF predicate at `0x0f000b00`. This new
trial stopped before management publication, so it neither confirms nor rules
out the hypothesis that a native PWRGATE handshake changes that outcome. There
is no new ACK, CPU-stop, paired-notification or strict physical-OFF result to
compare. No physical OFF, retirement, release, restart, recovery or rendered
pixel qualification follows from this boot.

The [bound JSON](2026-10-09-gfx-native-powergate-live-terminal-review.json) pins
the exact owner, header/source, receipt, preparation, native evidence and all
four saved captures. This review used saved files and pure command admission
replay only; it performed no hardware action or live register read. A future
admission change must preserve this consumed owner and expose or bound the
mailbox condition in a separate candidate.
