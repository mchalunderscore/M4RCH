# Retained native power-cycle live startup and first OFF — 2026-10-09

Fresh boot `5bf0a178-e6d8-4def-8088-74ad7ea87727` loaded the finalized
`abf4ef3c…` owner and published the same 69-page graph. Native ON wrote full
REQ `0→0x2000` and verified all three PMC votes. STATUS0 selected the reviewed
native bypass; it is not a PMP ACK or an inactivity observation.

Initial recovery completed 0 of requested 2 cycles and remained at phase2,
counter1, host-stop1, request-state0/request-flag1 and control32/32/32. The exact
`gfx-retained-power-cycle-session` marker qualifies the distinct four-command
contract. `gfx-retained-cycle` remains conditional on a successful saved first
OFF proof. The inherited cold interpretation/session prose still describes the
original first-stage commands; it does not supersede the new typed contract.
The baseline snapshot succeeded cleanly with physical word `0x1f0003ff`/BUSY0,
START set (`CTRL44=0x10`, `STATUS48=0x4e`) and held1/usage1/ACTIVE/error0.
All174 allocations remain represented; the56-page dormant render backing,
35-page job pool and all12 empty work cursor triplets are unchanged. The journal
remains50,410 records/status0/doorbells0 at startup and baseline.

The first terminal `gfx-powergate` then succeeded. This reviewer rebuilt the
actual frozen Python first-OFF proof from its original returned report, exact
raw captures and joined log delta, and matched root's saved seven-pin proof.
Its own202 native ACK and checked CPU stop precede paired OFF and the sole first
PM put. Strict physical word `0x0f000300` passes the unchanged mask; accounting
is usage0/suspended/held0/error0. All174 allocations are retained, with no work,
backing release or rendering. This establishes another first shutdown, not
successful reentry or a second OFF.

Root saved loaded GNU note/refcount1 after cold startup and before the terminal
intent. A separate identity extraction accidentally rewrote the ELF file layout
through in-place llvm-objcopy; root retained that rewritten artifact and restored
the candidate byte-for-byte from its immutable original before the baseline and
terminal commands. This reviewer checked both saved artifacts' hashes, the
restored compiled owner hash and equal GNU notes, and bound the correction
report. Source, receipt, kernel and loaded owner remained unchanged. No current
hardware or sysfs read was made by this reviewer.

All captures are separate non-atomic reads. The baseline's resident-active flag
means retained lifetime; usable=false/diagnostic=true reflects failed recovery.
Later second-epoch current ACTIVE/OFF values cannot be inferred from these
historical first-OFF fields. The second intent, its partial reentry and any
second OFF require separate actual evidence. Application rejoin, execution,
rendering and joined DMA retirement remain unproved.
[Bound raw startup and first-OFF inputs](2026-10-09-gfx-retained-power-cycle-live-startup-review.json).
