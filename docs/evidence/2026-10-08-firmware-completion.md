# Completion backing, firmware attachment and consumption

Private implementation-derived numeric research, matching AGX353.14/25G83.
No live allocation, GPU command, kernel change or reboot in this batch.
The firmware image matches the existing normalized TEXT contract; no instruction
bytes are excluded. Apple executable code is never included in exported artifacts.
Offsets below are hexadecimal.

The prior four-descriptor layout is now linked to its native initialization
caller and matching firmware consumer. This is preparation for a Linux-owned
completion path; it is not evidence that a GPU job has completed.

## Allocation and hardware attachment

`allocSingleKSMCompletionQueue`895fe24..8960064 is checked in1,024 complete
wrapper calls:292 successes and732 service failures. Cases cover allocation,
inner initialization, device/firmware mapping creation and null mapping-address
failures, plus preexisting mappings. Output is only written after success;
failure releases the allocated object and preserves the supplied output slot.
Full resource/accelerator/output bytes and service argument/order match.

Resource10 receives the inherited type word. `initInner` receives requested
bytes and low32 accelerator18e00 OR23. Device-context lookup is external.
Both mapping objects come from **the same resource48 provider**:

| Resource field | Mapping context | Mapping flags | Address getter |
| --- | --- | --- | --- |
| 58 | device-context service | 600000087 | virtual158 |
| 50 | resource18 | 20900000084 | virtual158 |

These are external Apple mapping service arguments, not Linux PTE bits. The
wrapper doesn't establish actual allocation destruction or cache policy. Do not
create two unrelated physical completion buffers just because there are two
descriptor addresses. Underlying `initInner` and mapping service semantics
remain explicit audit fixtures.

The G16X vtable address point7eae388+10, slotd68 resolves to89d76c0.
Firmware-data caller89cd41c..89cd44c passes firmware2b8+2620 as the descriptor
destination; accelerator298 is already inX0 on entry.512 actual caller/builder
compositions compare whole hardware, firmware and accelerator backing, covering
all16 presence masks. The populated array occupies hardware2620..269f.
Hardware is the object pointed to by main0 in the existing initialization graph.
This attaches fields numerically; live graph ownership/cache/publication remain
separate work.

## Matching firmware ring traversal

Actual complete helper15200..15d08 runs in1,024 emulated-RAM cases. This batch
uses already-held reference counts and disables optional EB8, tracing and
pending-notification paths. Modes0/2, capacities2/3/10/100, every presence mask,
empty/full/wrapping rings, and software cursors both agreeing/disagreeing with
the hardware head are covered. Native descriptor order comes from TEXT58a64.
The JSON records the exact order rather than assuming array order.

1,792 nonempty batches traverse71,168 entries and issue47,451 fixture payload
processing calls;256 present empty batches,512 full batches and655 wrapping
batches pass. Entire descriptor, firmware-global RAM, MMIO fixture and ring
backing compare with independent expectations. MMIO is ordinary emulated RAM;
no hardware register side effects or cache behavior are established.

| Descriptor field | Observed firmware use |
| --- | --- |
| 0, u64 | Presence gate/device address |
| 8, u64 | Firmware-accessible entry array |
| 10, u32 | Capacity |
| 14, u32 | Stride, native builder sets40 |
| 18, u32 | Hardware register selector0..3 |
| 1c, u32 | Software consumption cursor; builder initializes0 |

Hardware status offset is21168+8*selector. The u64 read is split through W
registers: low16 hardware head, next16 available count. High32 bits are ignored
by this path. **Entry traversal and cache-range preparation start at the
descriptor's software cursor**, not the hardware head. The read head is useful
for discrepancy diagnosis but isn't a replacement for that cursor.

The normal drain advances cursor modulo capacity per entry. Cache preparation
calls cover up to two wrapping ranges; a full batch first covers the whole ring,
then issues two zero-length calls. After consumption, a clock service contributes
to a firmware timestamp, and the helper writes the consumed count to MMIO
21188+8*selector. These status/ack offsets are relative to the firmware's
global18f6d0 register base. Do not infer a physical mapping without tracing that
base; this batch adds no MMIO whitelist permissions.

Mode2 runs through all selected entries. Mode0 has optional budget/notification
paths; this fixture supplies a budget larger than capacity. Cache service3ca80,
payload gate12564/process12788, notification flushing and clock behavior are
explicit service substitutions. Consuming a record is not by itself a verified
draw retirement, fence signal or safe allocation release.

## Payload extraction and saved-capture decoder

Actual handler prefix12788..12850 runs in1,024 random cases, phases1/2/3 and
both low pointer flags, against `firmware_completion.decode_entry`. Phase0
diagnostics and the remaining large payload handler are excluded.

Header word0 yields low kind bits0..2, phase bits4..5, mode bits6..7, queueID
bits9..15, and a40-bit epoch assembled from bits16..47 then bits48..55. The
metadata offset used by the guard is `(word>>39)&1fe00`. These are observed
field extractions, not complete protocol names/semantics.

Words20/28 are masked to54 bits. Word30 supplies a pointer with its low flag
bit cleared; the native prefix requests cache maintenance for4 bytes and reads
that u32 into a saved field. Word38 supplies another pointer and receives an
a8-byte cache-maintenance request. The latter is not simply another four-byte
stamp. Remaining processing and notification writes still need investigation.

`decode-completion-capture.py` accepts a saved hardware buffer, four saved status
words and four saved ring inputs. It checks geometry, emits cursor/head
disagreements, ordered entries and observed fields, and always reports
`retirement_verified=false`. It performs no live reads, acknowledgements, cursor
writes or release. Four capture tests cover wrap/full, incomplete backing,
invalid status, explicit integer handling and payload extraction.

Example manifest, paths relative to that manifest:

```json
{"hardware":"hardware.bin","statuses":["0x10000",0,0,0],
 "rings":["completion0.bin",null,null,null]}
```

Run only on captured buffers and record capture atomicity/cache state separately:

```sh
python experiments/t6040-gpu/decode-completion-capture.py capture.json decoded.json
python experiments/t6040-gpu/completion-capture-tests.py
```

## Remaining first-job work

Join initialized PM backing to full ordinary retention and actual TA caller
ordering. Build matched TA/3D work/microsequences from explicit resource inputs,
not the base-M4 donor files. Integrate Linux-owned physical backing, both address
domains, work/root/KSM queues/events and shader/target/context storage. Check
cache-visible publication and the completion payload handler's job identity,
stamp/notification/retirement relationships before readback or resource reuse.

The running failed warm INIT retains the graph probe; normal reboot is required
before live integration. No forced unload/reset or new warm INIT retry. Offline
work remains meaningful and no macOS handoff is needed for these next steps.
We are **not** at the point where only submission and result checks remain.

Reproduction receipts: private-completion-resource.json,
private-completion-attachment.json, firmware-completion-ring.json and
firmware-completion-fields.json alongside this document. All carry identity and
method-range hashes. Binary/TEXT/full disassembly stay private and local.
