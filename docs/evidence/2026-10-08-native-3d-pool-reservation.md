# Complete ordinary3D pool reservation and descriptor integration

The earlier private-3d-pool audit already established shared backing and mapping50/58 arithmetic. This extension executes the complete request89a6624..89a679c through actual descriptor caller895e788..895e7cc; no rediscovered address identity is claimed as new.

2,048 whole descriptor/firmware/occupancy checks pass:910 selected slots,980 full/zero-capacity paths,158 absent bitmaps.43 selected slots deliberately returnCPU0; native pool bookkeeping still increments occupancy/updates cursor and marks1348=1, then descriptor caller takes failure895eaf0. Absent bitmap returns0 without lock or updating1348. Full/zero-capacity sets1348=1 under lock. Lock/unlock and map158 callbacks check exact arguments/order but are explicit fixtures. Maps50 then58 reached through the same resource1320. CPU438 derives1328 plus displacement;440 derivesresource58 map;448 derivesresource50 map. Cursor/u32 slot*stride/u64 address wrap covered.

Reusable native_3d_pool.reserve arithmetic is now joined through optional ordinary3d_pool input in the paired builder. Requires occupancy bytes,capacity1..256,cursoru32,and explicit CPU/device/firmware bases; fixed checked ordinary3D stride2240. Candidates rejectzero/wrapping backing bases,mismatched register-slot address,unaligned mapped aliases and full pool. Exports updated occupancy and reservation receipt. CPU/exported service identifiers remain fixtures, not Linux allocations.

16 paired candidates pass80 list/scheduler links,64 TA FW values and23 malformed rejections.64 native prepared descriptor pairs now bind shared-slot aliases and derive scheduler payload from the reserved firmware alias rather than zero constructor storage. No physical pages, real mapping contexts/cache attributes, native locking/concurrency or retirement proven; submission_ready=false. No GPU hardware trial or rendered pixels.

Next execute pool backing creation/mapping path to qualify size,contexts and flags; then implement actual Linux-owned allocation/cache/queue graph and live submission/completion. Same-resource provenance does not prove the two virtual addresses are interchangeable.
