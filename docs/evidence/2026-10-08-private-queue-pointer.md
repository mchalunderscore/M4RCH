# Matched AGX command-pointer publication

Private-derived from AGX353.14 / Apple25G83. No hardware trial or kernel change.

## Two separate queues and cursors

`AGXChannel::writeChannelCommandPointer` at 0xfffffe0008981048 writes an
8-byte command pointer into the per-channel pointer array. This is separate
from the accelerator's 24-byte submission-record ring.

For the call-free path with optional tracking argument x3=0:

1. Load the queue-state pointer from host channel +0x60.
2. Read capacity at queue +0x60 and host write index at queue +0x40.
3. Compute `(write + 1) % capacity`; spin if it equals queue's read word +0x00.
4. Require current write index below host channel capacity at +0x54.
5. Write the supplied u64 pointer at `channel[+0x68] + write*8`.
6. Execute DMB ISH.
7. Advance queue +0x40 modulo queue capacity.

One slot is reserved to distinguish full from empty. A Linux implementation
should use a bounded wait/error path rather than copying the native unbounded
spin. Capacity-one queues are therefore unusable under these full/empty rules.
The queue's +0x50 sentinel from reset is not the host write index updated here.

The native method's second pointer parameter (x2) is unused in this reviewed
slice. Nonzero x3 selects additional host-side tracking using channel +0xe0,
+0xe8/+0xec/+0xf0 and may assert when the tracking ring is full. That path is
not covered by this audit, so do not infer that tracking may always be omitted
for real work from the numeric model alone.

## Link to accelerator submission

The `AGXWorkQueue::submitCommandToFirmware` block at
0xfffffe0008a2cad0 reads channel queue +0x40 into the first u32 of its
submit-info scratch (load at 0xfffffe0008a2cb60, store at 0xfffffe0008a2cb88).
This is then the low-16-bit value the accelerator-record encoder copies into
record +0x14. Thus the transport carries the queue's current next-write index,
not the address of the command itself. A single pointer appended at index N
advances this boundary to `(N+1)%capacity`; that boundary is the submission
argument observed here. The complete caller ordering still needs tracing.

The block additionally stores incremented channel +0xdc at scratch +4,
channel +0xf0 at scratch +8, and a scheduler-related object's +0x48 u64 at
scratch +0x10. These host metadata fields are not yet assigned protocol names.
Do not mistake the channel +0xd0 host pointer array written earlier in this
block for the firmware pointer array at channel +0x68.

## Verification

`audit-private-queue-pointer.py` pins the matched binary hash and executes the
reviewed native slice in emulated RAM. An independent model in
`private_queue_pointer.py` agrees for every write index at capacities
2/3/16/256: **277 successful publications and 277 full-queue cases**.
Wraparound, preservation of other queue/ring bytes and full-queue absence of
writes are checked. The full native loop is stopped by an instruction bound;
the numeric model returns would-block. DMB's opcode is checked; emulator RAM
does not establish hardware/DMA coherency. Optional tracking, error paths,
doorbells and live firmware consumption remain unverified.

## Next actions toward a first job

- Trace the command object's encoding and address supplied to this writer,
  starting with the native NOP/barrier path and then TA/3D job constructors.
- Resolve state +0/+8/+0x10 pointer roles, queue-state mapping, allocation
  ownership and required cache policy before creating live work queues.
- Corroborate queue boundary/cursor semantics against firmware consumers.
- First validate a complete job and completion notification, then a triangle;
  successful transport alone is insufficient for a GPU accelerated desktop.

The retained warm-failure probe still needs normal reboot before hardware work.
