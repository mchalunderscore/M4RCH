# Existing read-only reserved DATA sampler review

The saved sampler has no static blocker to one bounded DATA snapshot under the proposed loader guards. Its artifact SHA256 is `4c3bb5783f4d8164b817ee80ccb95f0e3cc8daf74d4041a03e9b03e0a708c25d`, byte identical to the frozen native-reset helper and bound in the current candidate receipt. The copied source also matches the maintained sampler source.

Direct AArch64 disassembly confirms fixed physical range `0x10001d44000..0x10001e7c000` (exclusive), size `0x138000`, a System RAM disjointness gate, WB temporary mapping, CPU `dc ivac` and `dsb sy`, then a full memcpy into its private buffer. It removes the temporary mapping before publishing the mode0400 sysfs file. The 13 imports contain no ASC, power, firmware, DMA-owner or GPU control entry. Normal exit frees only its private sample, kobject and sysfs file.

The observed EP1 address `0x10001de4000` and extent `0x1000` fit inside this fixed reservation at offset `0xa0000`. The corresponding preboot saved DATA bytes are zero. Existing post-event object/owned captures do not include that reserved DATA; the native EP1 report records crash/descriptor alternatives, without proving that this current frame is harmless or a crash.

The parent message proposes a fresh same-boot/owner-note/ref1/kernel/receipt/ADT/resource guard, absent sampler, durable exclusive intent/output, one insmod, one complete private sysfs copy, and normal sampler-only rmmod followed by unchanged owner verification. That plan is sound; its concrete loader implementation has not been supplied or reviewed here. This subagent executed no live guard or hardware action.

CPU cache invalidation does not prove firmware private-cache writeback freshness. Firmware may change bytes during the initial non-atomic copy. The resulting evidence cannot establish B20 completion, a second202, physical OFF, cessation, retirement or rendering. The adjacent JSON pins the selected source, compiled code/imports, current receipt and saved actual evidence.
