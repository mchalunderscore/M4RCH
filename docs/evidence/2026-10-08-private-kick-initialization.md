# Native kick-offset initialization and complete addKicks contract

Private-derived matched AGX353.14 / Apple25G83; offline only.

## Actual register-offset producer

`AGXAcceleratorG16::configureDevice` forms accelerator+`0xec90` at
`89d9bb8..89d9bbc`. Its native initialization at `89d9e00..89d9e14`
loads the 64-bit constant at `712d930` into fields+`0x198`/`0x19c`, then
stores16 at+`0x1a0`. Effective accelerator fields are:

| Field | Value |
|---|---:|
| `0xee28`: control offset | `0x4000` |
| `0xee2c`: count offset | `0x4008` |
| `0xee30`: bank stride | `0x10` |

This is the actual producer, distinct from the performance-map nibbles at
`0x18e28` etc checked in the preceding provenance audit.

## Connected complete native method

The initialization slice feeds complete `AGXKSMKickQueueG16::addKicks`
`89dc240..89dc394`. Tracing at accelerator1aed4 is disabled. Native code
selects bank9, therefore writes at MMIO base+`0x4090`, then base+`0x4098`.
Base is loaded from accelerator358; its provider/physical mapping remains open.

Control is `0x0020040000021018 | (queueID << 43)`. Count is the zero-extended
32-bit argument. Both stores are64-bit, in control-then-count order.

2048 connected cases cover queue IDs0..127 and counts0,1,2,127,256,65535,
0x80000000,0xffffffff in both accelerator6d3 bit3 modes. Large counts characterize
encoding; they are not asserted to be valid scheduler pending counts. Entire
accelerator/queue/MMIO fixtures are compared, including untouched bytes.

With bit3 clear, there are no provider callbacks. With bit3 set, the native
method loads object `accelerator5b0 -> firmware210`, calls its virtual58,
performs both stores, then tail-calls virtual50. The checker records the
combined callback/store order and verifies the callback receiver. The two
callbacks are synthetic no-op contracts, not emulations of their implementations;
no lock semantics or hardware ordering is claimed solely from their slot numbers.
PAC instructions are bypassed; native prologue/epilogue and both branches execute.

## G16X mode producer

The native G16X configuration slice `89ea4d4..89ea4e4` ORs
`0x0004000018020000` into incoming accelerator6d0 flags. In1024 randomized
cases it always sets bit27, which is byte6d3 bit3. Consequently this configuration
selects callback-bracketed writes unless later code changes that flag. This
check does not exclude later overrides or prove a running macOS flag value.

## Reproduce / next implementation work

```
python experiments/t6040-gpu/audit-private-kick-initialization.py \
  /boot/GPUC003/private-apple/com.apple.AGXG16X \
  docs/evidence/2026-10-08-private-kick-initialization.json
```

3072 cases pass. Resolve accelerator358 physical mapping and the firmware210
callback provider before using this write contract in a live Linux submission.
These offsets are relative to that base, not assumed relative to an existing
Linux SGX resource. Also preserve submission publication ordering; this audit
alone does not supply DMA/cache barriers or concurrent queue protection.

No actual MMIO, firmware consumption, job completion, shader execution or
rendered pixels is proved. No kernel/default changes. Retained failed warm INIT
still requires a normal reboot before hardware trials. No private binary or
full disassembly exported.
