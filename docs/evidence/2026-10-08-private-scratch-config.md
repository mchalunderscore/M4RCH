# Native scratch value enters the 3D scheduler configuration

Private-derived AGX353.14 / Apple25G83, offline only. This resolves the immediate
downstream destination of the completion scratch value. It is an opcode15
configuration field, not a direct fragment-register-list field.

## Connected native stages

The checker composes these real native stages in synthetic memory:

1. Complete getSKSMCompletionScratchRegValue at895ee3c..895ef28, including
   actual G16_SKSM channel payload getter89d5cf0. This uses the independently
   checked shared-counter/slot/generation/payload arithmetic.
2. Actual render-setup store8998c2c saves the returned value in descriptor2e8.
3. Complete common initKSMKickQueueConfigUpdateCommand at8987084..89871b0,
   including actual3D getDataMaster at895dc98 (returnsff) and an explicitly
   synthetic descriptor58 resource callback. This builds the common prefix.
4. Separately, start again from the original record backing and execute the
   actual3D submission prefix895bd00..895be14 continuously. This builds the
   common fields and overrides the completion-related fields below.

The two constructors are compared, not claimed to be consecutive calls in a
real submission. The actual3D submit path inlines the common construction;
the audit directly executes that path as well as the callable helper.

## Difference between common and 3D construction

All offsets/values in the table are hexadecimal.

| Record field | Common initializer | Actual3D submission prefix |
| --- | --- | --- |
| u32+22 | descriptor getDataMaster resultff | overwritten with1 |
| u32+26 | zero | descriptor2e2 bit0 |
| u64+2a | zero | descriptor2e8 scratch value |

The value at2a is copied even when the flag at26 is zero. In the real render-
setup caller, the branch on descriptor2e2 controls whether descriptor2e8 is
computed or cleared. Fixtures intentionally vary these inputs independently;
that characterizes the copier, not a reachable contradictory native state.

These fields are packed/unaligned. Preserve their widths and distinguish the
common descriptor callback returnff from the explicit3D field value1. The
remaining prefix through85 agrees with the existing independent config model,
including queue80/88 mappings, queue ID truncation, flags, descriptor144,
callback result and sentinel fields. The resource callback's semantic meaning
is still unresolved; it is not named a GPU completion callback here.

## Extent and remaining 3D overrides

The reviewed initialization writes86 bytes. Native config-pool stride is c0
(from configurePoolElementSizes field280 and runtime pool1598/stride15b8),
whereas the supplied writeup describes an88-byte wire record. Allocation
stride and wire extent are separate; the native stride does not contradict an
88-byte payload. Fullc0 fixture backing checks every preserved tail byte.

The prefix ends before the additional3D updates at895be14 onward: conditional
fields36/3e/46, descriptor-owner and channel callback fields, then publication
of descriptor468's GPU pointer. These remain outside this checker. It does
not execute the entire3D submit function, allocation, mapping or publication.

## Verification

```
python experiments/t6040-gpu/audit-private-scratch-config.py \
  /boot/GPUC003/private-apple/com.apple.AGXG16X \
  docs/evidence/2026-10-08-private-scratch-config.json
```

4096 cases pass both complete common initialization and actual3D prefix
construction after native scratch generation and descriptor store. They cover
signed counter banks, all256 payload bytes,32 table indices, flag masking,
identifier truncation, random preserved backing and explicit invalid-input
characterizations. Both constructors invoke actual native getDataMaster;
descriptor58 object's virtual1e0 return is supplied by a synthetic callback.
Full descriptor/accelerator/channel/scheduler/shared-backing preservation and
fullc0 destination comparison pass. Stack operations and vector constants
execute natively. PAC is bypassed. Binary/native ranges and vtable bindings
are pinned or recorded; DMA/cache/concurrency/firmware acceptance excluded.

## Implementation consequence

Linux's3D configuration builder must carry the generated scratch token in2a
and its controlling descriptor flag in26, after choosing the correct scheduler
and shared counter bank. A generic opcode15 initializer that leaves these
fields zero does not reproduce this3D path. Resolve the remaining3D updates
and notification/readback consumer before treating this as a complete job.
No executable draw, kernel/default change or hardware submission this round.
Retained failed warm INIT still requires normal reboot before hardware trials.
