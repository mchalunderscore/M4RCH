# Independent recovery dispatch review — boot 278a044e

The saved mask3 trial contains positive evidence that the main scheduler worker
continues to dispatch and return after the candidate phase2 recovery marker.
The remaining boundary is therefore narrower than a generally stalled main
worker. It still does not identify the live recovery PC or prove which semaphore
the recovery task is waiting on.

This review reproduced `out/recovery-dispatch/live-analysis-278a044e.json`
exactly from the saved capture. All eight matched firmware ranges in the pinned
worker ACK proof also match this boot's saved TEXT. The journal contains 50,458
records, including 42,052 trace records, with status zero and strictly increasing
trace timestamps. The sole candidate role4 marker is sequence 22832, timestamp
3923330416, arguments `(0, 0x1000, 4, 0)`, after host prefix 22823. The host ends
with counter1/phase2, controls32/32/32 and a sealed session; no work was submitted.

After that marker, 23,416 trace records contain 3,003 uninterrupted main dispatch
entry/exit pairs:

| Handler mask | Pairs after marker |
|---|---:|
| `0x1` | 601 |
| `0x2` | 601 |
| `0x4` | 601 |
| `0x10000000` | 600 |
| `0x20000000` | 600 |

The first triplet at sequences22835–22840 clears pending masks7→5→4→0, in handler
order2,1,4. Every observed entry has main hold zero; every observed exit has held
pending zero. This is consistent with recovery's mask7 publication being
serviced. Periodic publishers also generate these masks, so the trace does not
uniquely identify their publisher. No postmarker entry or pending argument
contains bit25 (`0x2000000`). Missing bit25 events do not prove an unpublished
event, a particular PC, or a wait on semaphore430.

The complete native sampler loop `0x3ad94..0x3b2b4` has exactly two direct trace
producer calls, at `0x3af54` and `0x3b254`. Both use trace-mask bit6 and event612
functions1/2 on the separate long sampler input-bit2/mask4 path. Normal recovery
input-bit3/mask8 acknowledgement signals semaphore`0x18e430` at`0x3ae48` without
either producer. Adding bit6 cannot directly observe that normal ACK. Its absence
would provide no stronger normal-ACK conclusion.

The next useful investigation is the normal sampler event8 notification and ACK
contract, including the real RTKernel wake, signal and recovery-wait functions.
Another boot solely to add bit6 has weak diagnostic value. Keep the session and
DMA backing pinned, and avoid repeating mask3 or failed START/INIT wakes.

The joined normal sampler/RTKernel investigation also executed19 RAM cases using
the actual notify`0x4518c`, task registry and state setter`0x4528c`, signal
`0x458d0`, recovery wait`0x45a54`, and IRQ-lock instructions. This extends the
earlier audit that intercepted notification and signaling. Only pointer
authentication and real asynchronous context switching remain explicit
boundaries. One parked recovery fixture preserves its CPU context, executes the
real signal path, and resumes the native waiter to its successful return.

Notification scans blocked tasks whose wait pointer`TCB+0x18` equals the event
object, removes matching tasks, clears their wait pointer and queues them by
priority`TCB+0x28`. An already runnable registered task has its wait pointer
cleared. The native state2 setter then avoids blocking when that registration
was cleared. Pending event bits also persist when no registered waiter matches.
This rules out a simple notification-before-block lost-wake model under the
qualified kernel prerequisites.

Signal uses a retained binary semaphore: an early signal changes0→1, and the
later native wait consumes1→0. A registered single waiter instead leaves its
TCB pointer in the semaphore, state3 in`TCB+0x2a`, and a pointer to a wait frame
whose first qword names the semaphore. Signal clears that registration and
queues the task. The matching, wrong-pointer and already runnable notification
cases, both registration cases, both signal/wait orderings, hold redirection and
held-event propagation pass. The fixtures do not prove actual RTKernel
scheduling, captured cache freshness or live recovery completion.

A useful next observation must coherently bind sampler pending/held state,
sampler blocked/ready membership, the recovery wait frame and semaphore430 to
the same postmarker invocation. A persistent coherent semaphore containing the
plain recovery TCB pointer, recovery state3 and waitframe first qword430 would
positively identify the registered recovery waiter. Repeated off-core DATA reads
without a freshness/coherency contract cannot supply that evidence. Qualifying
a firmware-produced diagnostic or the actual provider/hardware reset is a
concrete prerequisite; no extra host graph or MMIO operand was discovered on
these normal kernel paths.

The reproducible harness is
`experiments/t6040-gpu/audit-sampler-kernel-wake.py SAVED_TEXT OUTPUT`. It rejects
firmware changes outside the two qualified boot metadata payloads, verifies six
numeric range hashes, uses exclusive output creation, and emits no private byte
dumps. Its19-case receipt is
`out/recovery-dispatch/sampler-kernel-wake-agent-278a044e.json`. The adjacent proof
binds the harness and output hashes. An instruction-byte corruption is rejected
before emulation.

An independent source review of the separate GFX reset capability helper found
no blocking lifecycle issue for the matched kernel. Exclusive acquisition has
no deasserted flag, get/put do not operate the reset line, and the private
consumer is released after its reset reference. The root's saved ENODATA result
occurred before consumer construction, so that lifecycle remains unexercised.
The matched config excludes delayed kobject release. Reusing this code with
`CONFIG_DEBUG_KOBJECT_RELEASE` would require an explicit rejection or stronger
module callback lifetime handling on constructor allocation failures; that is a
portability boundary, not a blocker on the recorded kernel.

Numeric source hashes, exact first/last pairs and coverage limits are retained in
the adjacent JSON. No hardware access, private firmware changes, candidate
changes, recovery completion, rendering or DMA retirement is established here.
