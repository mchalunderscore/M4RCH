# Native dispatch trial ready

The v15 candidate combines the native queue PID/subpriority correction, tracing through the draw, and full final DATA/page-table capture in one fresh-boot attempt. The previous pause-bit trial produced no pixels and is not repeated.

Candidate: `/home/alice/Desktop/m4rch/out/gfx-native-dispatch-contract/candidate`. Owner SHA256 `bd3ee4134d2ac69ea61268ce6372d4c8ff89b44707dd48f8735ab80eb1e0c474`. Source receipt `e8783d245414dfcffffbbb62d17b6cbf93ec91479c901ae78f0ff21d538203e4`.

The module build is clean. 16 actual C sanitizer cases and 35 essential host cases passed, including the actual C trace/pipeline fixture. Frozen unchanged qualification is composed without repeating its test suite. The actual preflight rejects the current consumed boot before candidate or live GPU reads. No new owner was loaded, and kernel/GRUB remain unchanged.

The selected four recipe bytes match the existing channel-state getters. This closes a concrete native ABI discrepancy; whether it prevents rendering is still experimental. The candidate restores shared tracing once after control33 and keeps it enabled through the single draw and 15-second observation. Full raw buffers are saved before optional log analysis and final read-only RAM snapshots.

The additional read-only snapshots from boot eff8 preserved the owner, power reference and original trial. Retained page tables resolve the selected global/BSS addresses to the expected DATA pages. Physical zero values alone cannot identify the firmware's active reason, PC or dirty IOP cache contents. Native callers preserve bit1; another arbitrary pause-bit clear has no established contract.

One manual reboot into the existing native-reset kernel is needed. Root then runs fresh preflight and the candidate once, saves pixels/completions/trace/DATA/page tables, and updates the restart guide. All submitted-work resources remain retained. Triangle rendering, safe teardown and rebootless restart remain open.

The JSON companion pins the selected build, source, essential checks, prior driver findings and retained RAM captures. Private Apple binaries remain local under `out/` or `/boot/GPUC003/private-apple/`.
