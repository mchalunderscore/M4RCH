# Native GPTBAT backing and preserve/zero paths qualified — 2026-10-08

Executed bounded actual native generic allocation89a-equivalent8a12cf4..8a12d14 and binding/zeroing8a12db4..8a12e70 slices from pinned AGX353.14. 512 allocation argument cases (103 supplied failures),256 new-table zeroing cases and256 inherited-table preservation cases passed, comparing complete randomized RAM images. Allocation and mapping services remain supplied boundaries, not executed native allocator bodies.

Generic allocation service receives arguments3,page_bytes,page_bytes derived from the page-shift global. Current14-bit G16 profile requests16KiB;12-bit alternate also checked. Do not infer undocumented option3 semantics solely from numeric arguments. A failure branches to initialization failure. Separate zeroing cases are independent and do not continue that failed allocation.

New table path zeros exactly page_bytes before storing descriptor, mapping object and CPU pointer into secureMonitor+10,+18,+20. Existing/protected resource path binds the same fields while preserving every table byte. Full initialization statically calls setupMMUConfig slot190 only on new path, then common slot1a8; the latter and preceding mapping lifecycle remain unqualified here.

One16KiB allocation can contain1024 16-byte context pairs by arithmetic; this is not evidence all1024 IDs are usable. Executed context registration domain remains0..127. Next stage an owned zeroed16KiB GPTBAT page with the owned device root and validate the qualified128-pair encoding, then qualify live table acquisition/current base before any publication. Preserve existing contexts if adopting loader state. Shader/target/parameter/event/queue backing still required for actual drawing.

Evidence:2026-10-08-native-gptbat-backing.json; experiments/t6040-gpu/audit-native-gptbat-backing.py. Both slices/binary hashes recorded. No hardware access, live context, accepted job or pixels; no reboot required.
