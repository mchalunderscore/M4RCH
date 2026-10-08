# G16 completion descriptors and allocation caller

Offline AGX353.14/25G83, private input SHA pinned in receipts. Numeric offsets,
addresses and record sizes below are hexadecimal unless stated in decimal.
No live allocation, GPU commands or kernel changes. This fills a preparation
gap; it does not establish completion delivery or command retirement.

## Actual native descriptor population

populateKSMCompletionQueue89d76c0..89d7948 writes four descriptors of20 bytes
each. It takes accelerator resource pointers from1af70/1af78/1af80/1af88.
For each nonnull resource, it queries resource58 virtual158 followed by
resource50 virtual158, and writes this record:

| Offset | Width | Value |
|---|---|---|
|0|u64|resource58 mapping158 result|
|8|u64|resource50 mapping158 result|
|10|u32|acceleratoree58 capacity|
|14|u32|40-byte entry size|
|18|u32|descriptor index0..3|
|1c|u32|zero|

Absent resource clears only descriptor0 (first address); the remaining18 bytes
are preserved. Thus zero backing must be intentional if an absent descriptor is
expected to contain all zero bytes. The native method itself does not sanitize
all absent fields.

audit-private-completion-queues.py runs1024 complete method calls, all16 resource
presence masks, random u32 counts and explicit mapping results. It compares the
entire80-byte output and unchanged accelerator bytes;2048 present and2048 absent
descriptors match the independent reusable model private_completion_queue.py.
All ordered mapping arguments are checked. Native constants at712d8e0 are
decimal `(64,0,64,1,64,2,64,3)`, matching the four entry-size/index pairs.

These are **64-byte completion entries, not the72-byte general firmware event
ring**. The two mapping roles are identified by object path, without assuming a
universal CPU-versus-firmware meaning from virtual158 alone. Native output does
not validate returned addresses or count/capacity against a real allocation.

## Actual native allocation caller

allocKSMCompletionQueues89d712c..89d71ec loads the same count at acceleratoree58
and requests `((count*40+ff)&7fffffff00)` bytes, through virtualf50
allocSingleKSMCompletionQueue. It first passes output slot1af70, then1af80.
It does not allocate the intervening descriptor slots1af78/1af88 in this method.
First failure returns without the second call. Second failure preserves the
first successful fixture output; cleanup must be qualified elsewhere. The
second call is a tail call, which the audit includes.

audit-private-completion-allocation.py runs1024 full accelerator comparisons:
512 first failures,256 second failures,256 successes. Ordered output slots and
requested sizes match the independent size model, including zero/max-u32
arithmetic boundaries. Those boundaries are not recommended live capacities.
Underlying allocSingleKSMCompletionQueue remains an explicit argument/order
checked service; its allocator/mapping/unwind semantics are not established.

## Linux integration implication and next steps

The current helper does not yet publish these matched native descriptors or
consume the KSM completion entries. Keep their layout separate from receive13's
general event decoder. Before publishing: qualify the root/shared-object field
that receives this array, choose a real bounded count, allocate the required
backing, establish both mapping identities/permissions, initialize absent
records deliberately, and track allocation failure cleanup.

Then qualify completion entry payload/cursor ownership, cache synchronization,
queue/event/stamp association and independent retirement. A moved prefetch/read
cursor or type1 event notification mask alone still does not prove a draw or
permit freeing GPU resources. The existing pixel checker must receive coherent
readback plus independent completion evidence.

Failed warm INIT remains retained. Normal reboot is required before live
integration; no forced unload/reset/warm retry. Submission-only readiness is
not established by these numeric descriptor/allocation audits.
