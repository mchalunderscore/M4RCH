# Independent native-status terminal review — boot 94cb4163

The completed STOP returned successfully, and the paired native OFF notification completed. The physical OFF attempt **failed the frozen predicate** with `-110`. The sealed host state admits only `sample` and `gfx-snapshot`; actual wrapper replay refuses control, recover, trace-off, submit, STOP and a second OFF. No reviewer hardware action or live read occurred.

The [bound JSON](2026-10-09-gfx-native-status-independent-terminal-review.json) verifies the exact candidate owner artifact (`asc-graph-init/asc-graph-init.ko`), all artifact/source pins, the cold capture and four operation captures: initial snapshot, STOP, OFF and the late snapshot. Every capture has complete objects/owned extents and matching report hashes; receive binary/decoded evidence stays identical. OFF has a terminal error with intact captures and `capture_errors=[]`, while the late diagnostic operation completes successfully. Both keep work intent false, zero completed recovery cycles, trace-off false, all 174 pages retained and reboot required.

STOP records START cleared, native idle and zero management packets. Native OFF records REQ 0x2000→0 with exact readback, three voter clears/readbacks, STATUS0 bypass and notification `off_complete=1`. The physical result records normal PM put result 0, usage 0, held 0 and runtime suspension, followed by `provider_off_observed=0`, `snapshot_result=-110`, retirement 0 and a consumed gate. Notification completion does not establish physical OFF or retirement.

All 101 valid after-OFF words are `0x0f000b00`, with ACTUAL=0/TARGET=0/AUTO=0 and bit11 set. Their first/last kernel timestamps are 392.470616/392.584665: the **measured poll horizon is 0.114049 seconds**. The printed `poll_min_delay_us=100000` is preserved as metadata; this review does not infer a 100ms interval from it. The late word at 654.809950 is unchanged, with held 0, usage 0, suspension and runtime error 0. ASC sampling and MMIO-after-OFF permission remain 0.

The saved power-field bytes changed during the sealed interval:

| Capture | Objects at 0x3652c | Owned at 0x3e52c |
|---|---|---|
| OFF | `f5630000` = 25589 | `f7630000` = 25591 |
| Late snapshot | `e0de0000` = 57056 | `e1de0000` = 57057 |

These are little-endian 32-bit values. Objects/log readings progress by 31,467; the separately read owned snapshot progresses by 31,466. Logged DRAM timestamps 392.584685→654.809965 span 262.225280 seconds. The separate capture times explain the small value differences. This establishes changed retained bytes; producer identity and global cessation remain unqualified.

Across cold and all four operations, all 56 render backing pages and 35 job-pool pages remain identical to their prepared bytes. All 12 work-channel cursor triplets remain zero, both deferred work rings remain unchanged and control stays 32/32/32. Target/completion/hardware completion storage stays unchanged. The journal remains 50,410 records with status flags 0 and doorbells 0. The candidate’s `graph_submit_work=false` describes startup auto-publication; its separate deferred-triangle capability does not imply a draw occurred.

The [independent startup review](2026-10-09-gfx-native-status-independent-startup-review.md) records the failed recovery and closed draw gates. This terminal review preserves the frozen OFF outcome and adds no retry, warm wake, release, restart or rendering qualification. Snapshots are non-atomic. All mappings/backing remain retained, and successful recovery, cessation and DMA retirement remain unproven.
