# Native GFX reset: independent live evidence review

On boot `a1f61d61-b0ec-4475-948b-e3de2741e60b`, the single version2 native command probe completed its defined writes and checks. RESET31 was observed set in its diagnostic assertion read; DEV_DISABLE10 remained clear. ASC state and application recovery did not change, and a qualified firmware-owned power counter continued increasing after the command completed. This establishes native command delivery and register observations, without establishing whole-GPU reset coverage, access cessation, repeatable recovery or memory retirement. The reviewer used saved files and performed no hardware operation.

The saved preflight matches kernel `7.1.13-m4rch-gpu-native-reset`, notes SHA256 `85c56f7a3d7409747dd67fe1dcbf8839562aafab16a9124f9304689a14de437d`, owner `51aeeab15ff4a369ce11717e24d7ba6507c176981eedfa3da61747b47959e432`, and build receipt `96d5dda793adf700017b5e28b33b2ee6e2964ab058a08ec4bcdcdf68fbe7909e`. All3 PD bindings and3 USB role providers were present. Gate1 shadow and gate2 retained startup succeeded. Initial controls reached32/32/32; recovery remained at counter1/phase2/request0,flag1 with0 of2 cycles completed. No work or triangle was submitted.

## Exact command and read receipt

The sole `gfx-reset` is saved in `resident-operations/20261009T162912.886666Z-gfx-reset-a726f035`, at kernel time2780.118855s. Return0, operation_error0, cleanup_error0, common.valid`0x6f`, command_attempts`0x1f`, read_attempts`0x3f`, sequence_completed1, release_command_verified1 and auto_policy_restored1 form a consistent complete primary receipt. There is no DEASSERTED stage; cleanup was not attempted.

Fresh AUTO-held state supplied `B=0x0f0000ff`, after clearing historical bits8/9. All five primary full-word bus writes returned0:

| Command | Desired full word |
|---|---|
| INHIBIT | `0x0f0000ff` |
| DISABLE | `0x0f0004ff` |
| ASSERT | `0x8f0004ff` |
| RELEASE | `0x0f0000ff` |
| RESTORE | `0x1f0000ff` |

All six primary read stages had one read, zero bus error and zero poll delay. BEFORE/FINAL read `0x1f0003ff`; AUTO_HELD/DISABLED/RELEASED read `0x0f0003ff`; ASSERTED read `0x8f0003ff`. Disable and assertion delays were each1us. Thus the first trial's unmet bit10-latch requirement was avoided, RESET31 was sampled set and then clear, and original AUTO was observed restored. These facts do not establish that every affected engine, ASC, cache or bus master reset. `release_command_verified` qualifies the forced release and checked raw conditions, not a physical isolation/drain boundary.

## State after the completed sequence

ASC CONTROL40/CONTROL44/STATUS48 stayed `0xf0401/0x10/0x4e` before and immediately after the command, through the post snapshot and sample. Counter1/phase2/request0,flag1 and controls32/32/32 remained unchanged in all seven captures. All36 work cursor words stayed zero; all256 TA entries were inactive.

The `objects-after.bin` snapshots independently show firmware-owned power+`0x652c` increasing:

| Capture | Power counter |
|---|---:|
| Initial owner |1217|
| Pre-reset snapshot |5537|
| Reset result |8102|
| Later post-reset snapshot |16396|
| Sample |17495|
| Stop capture |19384|
| Final sample about100s after stop |31351|

The increase8102→16396 after successful command delivery supports continued changes in qualified shared state. After the pre-reset baseline, owned snapshots change only pages6/14/15, containing extra_root and power; the initial-to-baseline comparison also changes pages53/54. These observations are not globally atomic and do not identify a particular execution engine. They contradict using this command result as evidence that all GPU access ceased.

The host receive journal remains byte-identical at50412 records/status0/doorbells0. Its draining worker was sealed, so this is expected host behavior and does not show firmware cessation.

The packet-free stop at2874.133s cleared CONTROL44 START once: CONTROL40=`0xf0401`, CONTROL44=`0`, STATUS48=`0x4e`. The matched V6 idle predicate `(STATUS48 & 3) != 0` passes with lowbits2, as it already did before the command and stop. The final allowed sample at2973.860s, about99.73s later, observes the same stopped/idle register state while the firmware-owned power counter rises19384→31351. Its separately read owned copy corroborates19385→31352; the one-count differences reflect non-atomic captures. Owned pages6/14/15 change by59 bytes over this interval. Thus neither the native command sequence nor START-clear/native-idle stopped the observed shared-state producer. These sampled control/idle predicates do not qualify DMA retirement; even stable memory would not establish it.

Owner and wrapper retain the consumed one-attempt gate, failed recovery state and host_stopped1. All174 pages, joined context, mappings and PM ownership remain pinned. The final history has gfx_reset_attempted=true, host_stop_requested=true, operation_failed=true, submit_attempted=false and no in-flight operation. Only bounded sample, read-only gfx-snapshot and idempotent packet-free stop remain admitted. No reset retry, warm START/INIT, recovery/control/trace-off/submit, new graph, unload, unmap/free or PM release is qualified. The companion JSON binds the initial capture, all six typed operations, final wrapper history, preflight and contract inputs.
