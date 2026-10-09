# Retained resident owner for the experimental GFX reset

The source now has an explicitly compiled `GFX_RESET_SCOPE_TRIAL` owner path.
It connects the reviewed driver-owned snapshot/pulse API to two typed commands,
`gfx-snapshot` and `gfx-reset`, while preserving the feature-off resident contract.
No kernel loading, hardware operation, reboot or boot installation occurred in
this implementation work. Root owns the future kernel/candidate build and its
exact artifact admission.

The source changes are limited to `asc-graph-init.c`, `recovery-cycle.h` and the
new `gfx-reset-scope.h`; generated graph, draw, pool, render and initial-mask bytes
are not edited. Feature-selected init requires the joined recovery fixture
without startup work, gate 2, a resident session, and no warm restart, automatic
shutdown or release request. The module marks its retained owner only after
acquiring the resident module pin under the graph mutex.

Reset admission requires phase 0/unsealed or phase 2/diagnostic-sealed, held active
runtime-PM ownership, the pin, mapped regions, installed root/retained context,
all 174 pages, no submitted work, all 36 work cursor words zero, no active record
among 256 TA entries, and equal consumed control cursors in 32..128. An admission
failure permanently consumes the reset gate without claiming an API attempt.
An accepted command sets the API-attempt flag and permanent session seal before
entering the pulse. A refusal or partial-write error cannot cause a retry.
Every result retains pages, mappings and power ownership.

Driver snapshot/pulse observations log the return value, full valid mask, every
valid register field, domain/reset-user state, automatic-policy restoration,
operation error and cleanup error. Invalid fields are marked unavailable and
never printed as meaningful values. ASC40/44/48 and retained protocol/journal
fields are sampled without receive draining or host publication. Snapshot
failure seals publication. After reset intent, sample uses this limited
protocol logger instead of receive handling or deeper GPU status sampling.

Feature stop is always packet-free, including the initial failed phase 2 owner:
it seals the reset/publication gates, cancels the worker, freshly clears ASC
START, and keeps the diagnostic resident owner. It issues no management/RX ACK
packet, PM put, unmap or free. Repeat stop is idempotent. Subsequent snapshot
and sample remain available, while control/recover/trace-off/submit cannot resume.
The worker shares `graph_io_lock`; nonsynchronous cancellation under that lock
avoids waiting on a worker that needs the same mutex. Its next entry observes
the seal and neither drains RX nor requeues.

The actual-C replay passed 513 cases with ASan/UBSan. It extracts the unchanged
owner header, typed handler, receive worker, actual idle checks and recovery
logger. Only ARM cache-clean assembly in the submit branch is replaced by a
recorder. MMIO, driver API, PM and transport are bounded recording stubs. Cases
cover every page/work/TA guard; phase and consumed-control boundaries; API entry
flag ordering and uncertain errors; every valid observation field and poisoned
invalid data; publication rejection, pending-worker behavior and stop before or
after reset. The existing feature-off actual trace/cycle/typed-handler replay
passed 88 cases. These tests do not repeat the driver's 98 fault-injection cases.

The independent owner reviewer reproduced all 513 cases and found no source
blocker. Its separately owned review binds the final code and records the
wrapper's separate admission requirements. The adjacent JSON binds source/test
and output hashes. Private old candidates are preserved; all implementation
outputs remain offline.

These checks qualify owner policy and serialization structure. They do not
qualify real kernel scheduling, provider/reset-user lifetime, hardware reset
coverage, firmware DATA restoration, recovery or whole-GPU DMA retirement.
The authorized experimental pulse remains permissible with backing retained;
no observed result here permits backing release after a pulse.
