# Independent retained-cycle terminal review — boot5bf0a178

The first native shutdown succeeded again, but the retained cycle refused
before START. Its one new PM reference restored physical ACTIVE; the sampled
ASC status was0x6c, whereas the frozen v6 admission requires exactly0x6a.
No second paired ON, START, protocol exchange,0x202, CPU stop, paired OFF or PM
put occurred. The second reference remains held. This establishes another
successful shutdown on a fresh boot, not a completed same-boot power cycle or
application recovery.

The [bound JSON](2026-10-09-gfx-retained-power-cycle-live-terminal-review.json)
contains91 input pins and verifies the cold, baseline, first-OFF, second-refusal
and later-diagnostic reports and raw captures. It binds owner `abf4ef3c…`,
receipt `1762f50d…`, selected source v6, the seven-file first-OFF proof and the
late read-only kernel log. This reviewer performed no hardware action, live
read or qualification replay. Frozen candidate/source/qualification files
remain unchanged.

Cold startup was a qualified diagnostic session with initial recovery failed,
zero completed recovery cycles and no work submitted. The first operation
sealed intent at261.823400. Eight removed frames were the exact EP32
notification0x0042000000000000. Admission copied766 journal records:511 trace
records and255 statistics records, with no controller-event ring additions.
The journal moved50410→51176, doorbells0→8, statusflags0. CTRL44 was0x10;
STATUS48 was0x4e while notifications remained, then0x6e at fresh empty RX.
Ten operand samples and one empty wait preceded the sole0x202 at261.824600.

At261.829038 the own ACK was0x0070000000000201, EP0 metadata,
after five polls. Fresh empty RX and native idle preceded checked fresh
clear0x10/clear0x20; both readbacks were0 and final STATUS48 was0x6d.
Paired OFF wrote PMP0x2000→0 and verified all three PMC votes. Native STATUS0
selected the separate PMP ACK-wait bypass; it was not a PMP ACK. The normal PM
put returned0, held/usage became0, runtime was suspended/error0, and the first
physical sample at261.829518 was0x0f000300, domainOFF/BUSY0. Result0,
snapshot_count1, provider-off-observed1 and accounting-ok1 establish that
first shutdown.

The second command consumed its own intent at288.315845. Fresh before-get
observation at288.315897 still had strict word0x0f000300. The original owned
identities and first-OFF evidence were qualified. One `resume_and_get` returned0;
the separately owned second reference had held1/usage1/runtime ACTIVE/error0.
The fresh physical word at288.315932 was0x1f0003ff, domainON, ACTUAL/TARGET15,
AUTO1 and BUSY0. The next four-operand sample at288.315935 had:

| Operand | Observed | Frozen v6 admission |
| --- | --- | --- |
| CTRL44 | 0x0 | Valid, START clear — passes |
| STATUS48 | 0x6c | Exact0x6a — refuses |
| RX114 | 0x20001 | Valid, EMPTY set — passes |
| TX110 | 0x20001 | Valid, FULL clear — passes |

The typed retained-return record at288.315938 gives result−16 and
`refused_condition=cold-boundary-unqualified`. It records all subsequent action
attempts as0, with second_ref_held1 and the original identities/evidence
preserved. The host received EBUSY and kept complete=false,
operation_uncertain=true and both intents consumed. Its final data capture is
clean; capture success does not turn the failed operation into host completion.
Default zero put/snapshot results with attempt0 do not prove a second OFF.

The admitted diagnostic at353.648340 freshly observed physical ACTIVE
0x1f0003ff and held1/usage1/ACTIVE/error0. ASC sampling was0. Frozen first
diagnostics still show provider-off-observed1, accounting-ok1 and host-stopped1;
those fields are historical and cannot override the new physical/accounting
sample. The later diagnostic-current marker at353.648362 confirms the second
reference and consumed intent. Its CTRL/STATUS/RX/TX values are the cached
288.315935 operands, not a fresh ASC read at353 seconds.

All69 objects pages, all174 owned pages and the complete raw journal are byte
identical between first OFF, the refused second cycle and the later diagnostic.
The separately saved power field remains19110, journal51176 and doorbells8.
The logged first-to-later DRAM interval is91.818832 seconds, spanning physical
OFF and the restored ACTIVE domain. These non-atomic observations establish
no sampled change in these retained buffers, not joined whole-GPU DMA
retirement. All56 dormant render pages match their fixture, all35 job pages
match cold capture, all12 work cursor triplets remain0, deferred work rings
match their fixture and control remains32/32/32. No triangle was submitted.

Long retained-cycle records have a bounded1021-byte payload and truncated
tail tokens. The immediate second capture lacks its final retained-return row;
the later capture exposes the same row with its original288.315938 timestamp.
Likewise, the immediate diagnostic capture lacks diagnostic-current, while the
late read-only OS log exposes its original353.648362 row. The source puts its
newline at the end of the full format, beyond the observed truncation. An
incomplete printk record becoming visible after an unrelated later printk is
the supported mechanism inference. Immediate omission is not evidence that
the helper failed to execute; missing tail fields must not be invented. The
late log supplies visibility, not another GPU or PMGR observation.

A root identity-extraction command temporarily rewrote the candidate ELF file
layout after cold load. The rewritten file is preserved, and the exact original
abf4 artifact was restored before the first control. The pinned loaded-identity
record matches the original GNU note and reports refcount1. This was a
software-file correction, with no source/receipt or loaded-owner change.
The consumed v6 owner cannot retry, compensate its held reference, alter its
cold predicate or publish application work. Application rejoin, same-boot
recovery, safe release, DMA retirement and pixels remain unproved.
