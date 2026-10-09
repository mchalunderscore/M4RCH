# Decision after the retained GFX power-off trial

On boot339b9e8e, the separate no-work owner loaded successfully and retained
all174 pages. Its one normal runtime-PM put returned0, usage reached0, the
consumer suspended and GFX software state became OFF. ACTUAL/TARGET reached0
with AUTO cleared. The strict independent OFF check nevertheless timed out:
all101 post-put reads and all three later diagnostics held0x0f000b00, with
BUSY11 set. Qualified firmware-owned shared state continued changing for
221.286seconds afterward: object power+652c40513→67067 and its separately read
owned copy40514→67068. All maps, context, consumer and the owner remain pinned.
No work or triangle was submitted; application recovery remains phase2.

The hardware trial included one START-clear write. Its immediate STOP returned
EAGAIN with status4c; the next read-only observation saw status4e and START0.
A narrowly reviewed helper durably preserved the known returned error and
confirmed the completed STOP in host metadata. It made no second hardware or
sysfs write. Its actual saved-pair qualifier and17 negative cases passed.
The subsequent C power-off gate independently rechecked all prerequisites.
Unknown or interrupted operation results are never generally reconciled.

The independent live review binds94 actual raw/input files. Root verified all
94 hashes. After OFF intent, only the frozen PMGR/software-accounting/retained
DRAM paths were used; every diagnostic explicitly skipped ASC sampling. The
normal PM call and provider ACTUAL0 are narrower than physical whole-GPU
cessation and do not qualify retiring joined buffers. The clock domain did
not produce a clean BUSY-clear boundary, and the observed shared writer kept
running. Another identical leaf reset or normal put would repeat consumed
trials without a new hypothesis.

Native analysis resolves several proposed omissions. The real GFX386 state
word is the physical transition selected by virtualGFX-ASC401. Virtual401 is
skipped by native physical PS writes. Native AFR385 policy forces it ON, so
the observed AFR parent remaining ON is not sufficient reason to power it
down. Native provider power handling after clock disable is a disabled-state
query; the firmware stop path supplies a null output and performs no extra
hardware operation there. Target0's conditional native bit11 wait expects0;
there is no selected expected-SET interpretation that rescues this result.
Mapper setActive reaches an IOResources property lookup, whose runtime service
remains unavailable from the saved kernelcache/ADT. No translation-disable or
drain acknowledgement has been qualified through that dynamic binding.

The next useful work is to identify selected native shutdown coordination or
that missing runtime binding, then make a distinct test with a concrete
hypothesis. There is no next hardware candidate ready. The current owner has
consumed its terminal gate and dropped its own PM reference. Only bounded
sample/gfx-snapshot remain admitted. Do not resume, STOP, reset, START/INIT,
access ASC/SGX/mailbox registers, reuse work, load another owner, detach the
consumer, unmap/free backing or unload the module. No automatic reboot follows.

Normal PM accounting, native idle and ACTUAL0 do not make recovery successful.
Completion, fresh firmware DATA, repeatable restart, safe teardown and pixels
remain required for the full Gravity GPU/Mesa/DCP desktop goal.
