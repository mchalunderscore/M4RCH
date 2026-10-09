# RX servicing works; the first recovery remains in phase2

Boot `bba7a8f2-e6d3-49b8-88ed-bc5be2d17c0a` ran the reviewed RX candidate
`f123d1dbe97705f1ad9bfe3b98aa1e4f33cea95ee7002de3a553ecbf98ce0650` once.
The boot-time `0-0c` PD initialization failure occurred before GPU activity;
one normal targeted reprobe restored it. All three PD drivers and USB role
providers were verified before the GPU trial. Original logs are preserved.

The host retained **8,399 valid RX14 statistics records over 32 ring wraps**,
with no journal errors, overflow, invalid cursors or unexpected messages.
Record types17/18/25/27/28 match the native validator. No event or completion
record was received. Proactive draining kept the mailbox doorbell count zero.
This qualifies consumer advancement and retention for the observed workload.

All initial controls reached32/32/32. Recovery accepted EP33 class86 token0,
advanced the counter to1 and reached phase1. The host acknowledged phase2.
Within the following five seconds the request state cleared2->0 and software
power38/78 reached0, but phase3 did not arrive. Final phase2, host_stop1,
request_flag1 and unchanged controls mean **zero completed recovery cycles**.

A later typed diagnostic sample at uptime369.325s still shows that state.
Power+652c increased600->1201 during the initial recovery interval and8897
at the later sample. This is an ordinary firmware counter, not completed
application recoveries; its exact transition/policy cause remains under study.
Sequential MMIO samples were mostly zero with transient auxiliary/PRC activity.
These reads do not identify the firmware PC or prove which wait it reached.

The matched firmware clears request state at6450 after its first power-worker
wait returns. If that observed clear reflects coherent firmware progress,
the unresolved path before phase3 at6594 includes a lock, optional32104 call,
three active-array clears and further worker acknowledgements. Two read-only
reserved firmware DATA snapshots retain an IRQ frame with ELR6410; only one
u64 changes between captures. Private-cache writeback and frame freshness are
unproven, so neither observation identifies the live PC. Receipts record both
extents, hashes and capture times. No new recovery or triangle publication
followed the failure.

The native idle defaults are2/40ms in RegionC+9b8/+9bc, while our inputs were
zero. The32 consumed opcode22 controls reach their mirror, whose enable flag
clears after copying. A later zero enable does not exclude consumption. The
next distinct candidate corrects those inputs and enables a native recovery
trace marker; see `2026-10-09-recovery-progress-candidate.md/.json`.

The module/context/all174DMA pages remain pinned with a sealed diagnostic
interface. Only typed sample/stop is permitted. Joined DMA retirement,
repeatable teardown and rendering remain unverified. A normal reboot is
required before another candidate; do not retry the known failed wake trials.

Raw capture: `out/gpc-rx-recovery/candidate/asc-graph-init/boot-bba7a8f2-e6d3-49b8-88ed-bc5be2d17c0a`.
The adjacent JSON binds the source receipt, firmware identity, snapshots,
handshake trace, statistics counts and later diagnostic observation.
