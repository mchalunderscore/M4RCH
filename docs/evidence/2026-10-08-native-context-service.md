# Native device context service chain qualified — 2026-10-08

Expanded the1024-case actual native context registration/removal audit through accelerator and G16 secure-monitor getter/invalidation bodies, replacing the previous opaque service boundaries. Whole randomized object/table images passed:877 registrations,147 removals,414 old-context invalidations (211 direct RAM-surrogate register accesses;203 checked external register-service accesses). Earlier geometry/update tests also passed in the same runner.

Pinned vtable slots: G16accelerator7eae388+16+11b0 ->895f11c getter; +1168 ->895f33c invalidation. SecureMonitorG16 table7ead9a0+16+168 ->89e6dac getter; +198 ->89e675c invalidation. Getter follows accelerator1aef0 -> secureMonitor20 CPU table pointer. Invalidation follows secureMonitor40 back to accelerator. It emits u32(context_id<<8 | flags) to GFX offsetd08030 and reads back. This composed audit covers flags0 used by registration, not all possible independent flags.

When acceleratorc774==1, native invalidation computes mapped register address from acceleratorf8e8 minus acceleratorc980 plusd08030 and performs direct store/read. Otherwise it calls writeGFXReg32 followed by readGFXReg32. The direct branch used an emulated RAM register; external services checked target/offset/value/order and supplied return. No hardware register access, live cache invalidation, context installation or rendering occurred.

The composed registration still clears both old entry valid bits, executes DMB, invalidates the old context, then writes replacement aligned physical root | ASID48 | valid1 and zero TTBR1 followed by DMB. Root physical provider remains supplied; cache coherency and GPU visibility unproved. No extra invalidation after replacement is inferred.

Next: trace full G16 setupMMUConfig, qualified GPTBAT allocation/base register atd0802c, and required cache/barrier operations before installing the owned device-root context. Existing owned notification binding remains tested and unpublished. No reboot or macOS currently required.

Evidence:2026-10-08-native-context-service.json and portable experiments/t6040-gpu/audit-native-context-service.py. Binary and native slice hashes recorded, no Apple executable bytes embedded.
