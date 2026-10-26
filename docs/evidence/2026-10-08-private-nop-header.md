# Native NOP kick timestamp and scheduler header

Private-derived from matched AGX353.14 / Apple25G83. No hardware trial.

## Correction: add-kicks carries a timestamp, not a kick address

The G16 scheduler queue vtable at 0xfffffe0007eac548, address point +16,
slot +0x148 resolves to `encodeNOPKickEntry` at 0xfffffe00089dc07c.
This is the slot called by `submitNopUnprepared` at 0xfffffe000897f024.
The caller saves the result as x27 and writes it into the packed kick command.

The encoder writes into its CPU backing array:
`queue[+0x78] + low_byte(queue[+0x48]) * queue.u32[+0x14]`.
It loads the previous u64 counter at queue +0x48 into x0, advances the stored
counter, and returns that old counter in x0. The following atomic pending
count update uses other registers; x0 remains the old counter on success.
Therefore the packed opcode-14 field at +9 (and alternate opcode-16 field
at +6) is a **scheduler timestamp**, not a pointer to a kick record.
The earlier packed codec helpers and evidence have been corrected accordingly.
A real kick record is selected in separately configured backing memory.

## NOP header arithmetic

The native header patch sets the low two kind bits to 2. It inserts low 47
bits of the scheduler counter shifted left by two, ORs seven bits of queue
identity at bit42, then sets two priority bits at bit59. It preserves selected
upper header bits. The intended 40-bit timestamp range described by the
uploaded spec is consistent with the non-overlapping timestamp/queue fields.
The native shift masks 47 source bits, so out-of-range counter bits could
interfere with queue identity; do not advertise all 47 as a valid timestamp.
The numeric model intentionally retains the native behavior for malformed
inputs as well as normal values.

The counter advances its low-byte slot modulo queue capacity, increments the
middle portion by 0x100 when that slot wraps, and preserves upper 24 bits.
A Linux caller must distinguish this scheduler counter from a firmware GPU
address, accelerator queue boundary and completion stamp.

## Additional construction observed, not yet modeled as a full record

The encoder includes prior-timestamp dependency state, four u64 event-mask
words at record +0x128..+0x140, payload-derived values at +0x10/+0x18,
selected descriptor clearing at +0x150..+0x168, and a DMB before counter
advance. When no prior entry is cached, it calls external-state-dependent
`convertEventMachineTSToHWTS`; therefore simply zeroing these objects and
running the header patch is not a complete NOP constructor.

No native allocation, external timestamp conversion, pending-count atomic
operation, complete kick encoding or live GPU execution occurs in this audit.

## Verification

`audit-private-nop-header.py` pins the matched binary, the method-slot target
and return-value/caller sites. Two call-free instruction slices are emulated
against independent numeric models:

- 1,024 randomized header cases, including preserved bits and input masking;
- 834 counter cases across capacities 1/2/3/16/256, all slot positions and
  three high-bit patterns, verifying both stored next counter and old x0 value.

Capacity-one tests characterize counter arithmetic only; they do not override
the separate pointer-ring requirement to reserve one slot. No test establishes
hardware cache coherency or firmware acceptance.

Next qualify scheduler configuration/backing, timestamp dependencies and
entry signal masks. This corrected interpretation avoids sending an address
where firmware expects a scheduling timestamp. Current retained warm failure
still needs a normal reboot before hardware testing.
