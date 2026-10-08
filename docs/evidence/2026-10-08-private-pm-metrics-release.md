# Native metrics release and allocation cleanup decision

Offline AGX353.14/25G83; input SHA and method byte-range SHAs are pinned in the
JSON receipts. Numeric offsets and method addresses below are hexadecimal.
No GPU commands, live allocation teardown, kernel changes or reboot.

audit-private-pm-metrics-roundtrip.py adds actual releasePMPageMetricsBuffer
89f6ca0..89f6ea4 and actual releaseAllocationBlockIfPossible89f6ea4..89f70d4
to the request audit.512 successful request/release pairs compare complete
pool, bitmap, allocation-record and output bytes. Another512 empty-pool requests
remain checked. Allocation records start with a positive count; the request
increments it and release restores the original count and availability bits.
Actual allocation-release decision executes but keeps backing while still in use.

Release locks pool38, validates the slot against pool50*pool60, decrements the
selected allocation record's0 count, asserts the slot was allocated, sets the
inner free bit and corresponding outer availability bit, calls the allocation
cleanup decision with block index and force=false, then unlocks. Caller PM input
is unused on the qualified path; invalid slots/double releases assert and are
not executed by this audit. Resource-output references are not released by this
method, so these pairs do not establish full retained-resource destruction.

audit-private-pm-metrics-block-release.py checks1024 complete native allocation
cleanup calls:512 nonzero-count exits and512 zero-count frees. Block indices0..7,
slots per block8/32/64/128, force flags0/1, and partial/full/multiple bitmap words
cover29696 cleared slot bits. The independent model clears exactly that block's
slot range, and clears an outer bit only if its inner bitmap word becomes empty.
It checks all pool/bitmap/allocation-record/vector bytes.

For zero count, native code invokes pool virtual8 freeAllocationBlock with the
record, clears the selected block-vector entry, subtracts pool60 from poola8,
and decrements pool54. For nonzero count it preserves all bytes. The vector has
16 entries and tested indices are not the last, so replaceStorageArrays and
last-block shrink remain unqualified. Encoded vector span uses zero upper bias.

Actual underlying freeAllocationBlock remains an argument-checked no-op service.
Mutex, retain, mapping and support services in the roundtrip remain fixtures.
Thus this establishes native decision/bitmap/accounting behavior, not actual
allocator destruction, DMA ownership, coherent publication or firmware job
retirement. Join with initialized-job/ordinary retention and qualify last-block
shrink, actual allocator/root/work/queues/events and completion/readback next.

Reproduce each tool with the private binary path followed by the corresponding
docs/evidence/2026-10-08-private-pm-metrics-NAME.json output path. Do not export
the binary or full private disassembly in the handoff bundle.
