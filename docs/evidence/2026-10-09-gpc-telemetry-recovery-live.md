# Telemetry mapping: controls consumed; host stopped on normal notifications

Boot `f5f3a7cc-53aa-4fb1-9a60-3d8270925cfc` ran telemetry candidate
`0c7c32b00592aa0d42a2a96313e26fe87a426175f03b17739a125ecb5bfd8f3d` once.
Fresh preflight verified no GPU module and all three PD and USB role providers.

Initial controls reached **32/32/32**. The previous slot9 crash did not recur:
none of the 64 observed application messages came from crash endpoint1, and
the saved crashlog header remains `efefefef`, not `EHLC`.
Every observed message was endpoint32 payload `0042000000000000`, the normal
receive doorbell in both the matched Apple driver and Gravity.

The experimental host stopped at its 64-message observation cap after about
0.44 seconds. Its `if (!observed)` condition then skipped recovery because it
treated all mailbox activity as an error. Shutdown also encountered a normal
doorbell first and immediately failed `power_ack` without waiting for its
management response. These are host transport errors, not evidence of a new
firmware crash or a missing power acknowledgement from the device.

Receive14's statistics ring had consumer0, producer255 and 255 pending 72-byte
records. Their types are17/18/25/27/28, all accepted by the native statistics
validator. Its full-ring path sends the observed doorbell, rereads the consumer
a bounded number of times, then drops the new record if still full. A full ring
loses telemetry; this alone does not prove that startup is blocked.

Native cursor consumption was replayed against all 255 captured records:
copies match exactly, only the host consumer at state+0 changes, and producer
at+20 remains untouched. The endpoint handler sends no direct mailbox reply.
See `2026-10-09-rx42-stats-drain.json` for instruction and capture hashes,
validator capacities/masks, actual native replay and event0's no-op callback.

No recovery packet or triangle was submitted. The twelve work roots remain
empty; recovery counter/phase/request remain0. Final power38/78=0,
down_active63c8=1 and up_count652c=64 describe ordinary firmware power state,
not 64 application recovery cycles. Final ASC control/status0/4e followed the
host stop. No DMA retirement is proven: main module, context and all174pages
remain pinned, with both resident and diagnostic interfaces inactive.

Raw capture:
`out/gpc-telemetry-recovery/candidate/asc-graph-init/boot-f5f3a7cc-53aa-4fb1-9a60-3d8270925cfc`.
The adjacent JSON records exact state and hashes. The next candidate fixes
receive servicing across observation, recovery, resident idle and shutdown.
