# Native KSM resource address pair v7

The native scheduler ring has one backing allocation with device GPU, firmware
GPU and CPU virtual address views. `AGXKSMKickQueue::init` at
`89ee398..89ee718` retains one `AGXInternalResource` at queue `+70`; that resource
owns one `IOGPUSysMemory` object at `+48`. Both GPU mapping creation calls and
the CPU descriptor getter use that same object. The existing
`prepare-owned-scheduler-pair.py` orders its config pointers correctly as
`(device KSM ring VA, firmware KSM ring VA)`. Its builder aliases each ring page
into both address spaces; the native source confirms that single-backing
contract, rather than two independent ring allocations.

| Queue address | Resource view | Native association |
| --- | --- | --- |
| `+80` device GPU VA | GPU mapping `+58` | Accelerator GPU task at `+d0`, options `0x600000085` |
| `+88` firmware GPU VA | GPU mapping `+50` | Firmware task copied from accelerator `+11920` to resource `+18`, options `0x800000084` |
| `+78` CPU VA | CPU mapping `+60` | Memory descriptor obtained from the same resource `+48` backing |

Matched IOGPUFamily closes the previously opaque virtual calls. Backing virtual
`+150` resolves in both `IOGPUMemory` and `IOGPUSysMemory` to
`IOGPUMemory::createGPUMappingInTask(IOGPUTask*, u64)` at `a7c3af0`.
Mapping virtual `+158` resolves to `IOGPUMemoryMap::getGPUVirtualAddress` at
`a803200`, whose leaf returns mapping `+28`. Mapping initialization at
`a802e2c` retains the supplied memory object at map `+18` and task at map `+20`.
KSM checks the device mapping's task identity at `89ee60c`. The device task
getter is the actual `IOGPU::getGPUTask` at `a7f9f18`, returning accelerator
`+d0`; it is not a generic substituted mapping-service name.

The selected G16X accelerator's `+8e8` slot is the actual IOGPU mapping factory
at `a7f83a0`. Its `+9b0` slot resolves to `AGXAccelerator::newMemoryMap` at
`8967098`, which calls the selected `+a98` HAL factory at `89d9b10`. That
factory selects `AGXLegacyMemoryMap` when accelerator `+ecd4` is zero and
`AGXSecureMemoryMap` otherwise. Both actual subclass vtables inherit the same
`a803200` GPU VA getter at `+158`, so the interpretation does not depend on
inventing a runtime policy value. Matched kernel `IOMemoryMap` virtual `+138`
resolves to `getVirtualAddress` at `bf9b88c`; its leaf also returns its own
mapping `+28`, establishing the CPU-view interpretation independently.

Native requested size is computed in wrapping u32 arithmetic at `89ee420` as
`(capacity * record_bytes + alignment - 1) & -alignment`. `initInner` rounds
the resulting size to the kernel page size before creating its single backing.
Queue `+10/+14` retain record size/capacity; initial sequence is stored at
`+90/+48/+50`. Native `prepareMappings` and `completeMappings` operate on both
GPU views `+50/+58` under the same resource's prepare count `+38`. A second-view
prepare failure completes the first view. IOGPU's mapping prepare/complete
methods delegate through the retained backing at mapping `+18`.

Integration should retain one resource owner, map the same backing pages into
the selected device and firmware spaces, supply the two VAs in the proven
order, and retain both mappings through retirement. Different VAs are allowed;
independent physical ring contents violate this native ownership contract.
The numeric source closure does not prove current Linux page-table installation,
permissions, cache synchronization, native concurrent lifetime, firmware ring
consumption or GPU execution.

Saved numeric report:
`docs/evidence/2026-10-11-gravity-native-t6040-ksm-resource-v7.json`.
The adjacent `prepare_ksm_resource_evidence_v7.py` pins the matched AGX,
IOGPUFamily and decoded kernel hashes, resolves the chained vtable slots,
checks the getter leaves and saves source-span hashes. It exports no private
instructions. This was static offline investigation only: no new execution
tests, old audit reruns, hardware operations or frozen-source changes.
