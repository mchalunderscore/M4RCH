# Native 3D completion scratch value and producer provenance

Private-derived AGX353.14 / Apple25G83, offline only. The complete native
AGX3DCommandDescriptor::getSKSMCompletionScratchRegValue function
895ee3c..895ef28 executes, including the actual G16_SKSM payload getter.
This proves a value-construction path, not firmware completion delivery.

## Object selection and shared read

All offsets/addresses are hexadecimal; formula bit counts are decimal.

- Channel18 supplies the signed event/scheduler index. Fixtures use0..31.
- Descriptor10 supplies accelerator; scheduler is tablef938[index].
- Scheduler68 -> owner140 -> shared event-machine backing.
- If the signed32-bit argument is nonnegative, select backing1458; otherwise
  select1460. Index stride is18 hexadecimal (24 decimal).
- LDAR loads the selected64-bit shared counter with acquire semantics.
- Capacity is scheduler10; initial packed position is scheduler90.
- Channel vtable slot220 supplies a payload. The actual G16_SKSM vtable
  7eaa8e0 resolves to89d5cf0, which returns channel204 byte. The checker executes
  that native method instead of substituting a callback return.

## Independent arithmetic model

For unsigned32-bit argument `a`, shared u64 `counter`, initial u64 `p`, capacity
`n` and channel byte `payload`:

```
delta = (((counter << 24) | (a >> 8)) - 1) modulo 2^64
(q, r) = divmod(delta, n)
total = (p & 255) + (r & 255)
(wraps, slot) = divmod(total, n)
generation = ((p >> 8) + (q & 0xffffffff) + wraps) modulo 2^32
result = (slot & 255) | (generation << 8) | (payload << 40)
```

The result carries a low8-bit slot, next32-bit generation and payload byte at
bits40..47. It is not just a raw timestamp, MMIO register address or completion
stamp. The counter shift truncates to64 bits; arithmetic must preserve the
native widths. The slot calculation uses an8-bit remainder before rebasing.

Zero capacity is deliberately characterized using AArch64 UDIV's zero result
and native remainder arithmetic, not accepted as valid initialization.
Capacities above256 and oversized counters similarly characterize width effects;
they do not establish supported hardware input ranges.

## Where the value enters render preparation

Static caller at8998b68..8998b90 obtains an external event-machine value,
saves it in descriptor2f0 and, when descriptor2e2 bit0 is set, calls this native
method. Store at8998c2c writes the returned scratch value to descriptor2e8.
The alternate branch8998c24 supplies zero. The checker pins the store opcode;
it does not execute that external provider or full render-setup caller.

This extends the earlier independently audited NOP event-machine timestamp
conversion: the 3D path also supplies the channel payload and records the result
in the descriptor. We must still trace its downstream shader/register consumer
and the actual completion readback path before assigning a fence contract.

## Verification

```
python experiments/t6040-gpu/audit-private-completion-scratch.py \
  /boot/GPUC003/private-apple/com.apple.AGXG16X \
  docs/evidence/2026-10-08-private-completion-scratch.json
```

4096 cases cover both signed banks, argument boundaries, counter boundaries,
all256 channel payload bytes,32 table indices, multiple capacities and initial
positions. Complete native method + native payload getter agree with the
independent arithmetic model. All descriptor/accelerator/channel/scheduler/
owner/shared-backing bytes remain unchanged. Stack save/restore runs natively.
PAC is bypassed and fixtures are synthetic; LDAR runs in emulator RAM, which
proves neither concurrent ordering nor DMA coherency. Binary, method and getter
hashes, real vtable target and caller-store hash are recorded.

## Event-worker trace boundary

The event-type9 enqueue at89a34dc..89a357c signals accelerator470's event source.
Creation at896fbf0..896fc14 registers native callback8975214, named
allocateUMAMemoryEvent. Its available body is a no-op. This queue is not an
established render-completion dispatcher; do not use that trace as proof of
job retirement. Other firmware channels and event-machine provider behavior
remain candidates. No hardware/kernel/default changes or executable draw.
Retained failed warm INIT still needs normal reboot before hardware trials.
