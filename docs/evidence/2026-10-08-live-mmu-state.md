# Live MMU enabled with empty reserved context table — 2026-10-08

Fresh ADT captured this boot confirmed SGX primary288000000/3758000 and secondary288d00000/16c000 windows. Built exact13-register readerW=1, held existingGFXgenpd, read288d08000..288d08030 at the offsets qualified by native setup/invalidation, unloaded reader and power helper. Runtime suspend returned0. No MMU register writes or firmware start.

Observed control288d08000=1;mode04=3ff;08=1;14=3680d8;18=3680d8;0c/10/1c/20/24/28/30=0. Base register2c=417ffee -> physical105fffb8000 via native14-bit page-number shift. The additional0x360000 bits compared with cold native0x80d8 remain unexplained; preserve them rather than replacing with cold defaults. Native setup would early-return on control1 and never replace the base.

A separate read-only sampler checked that105fffb8000/4000 is disjoint from Linux System RAM, invalidated CPU lines, and copied the reserved page. Snapshot16KiB is entirely zero: no nonzero16-byte pairs among1024 positions. SHA2564fe7b59af6de3b665b67788cc2f99892ab827efae3a467342b3bb4e3bc8e5bfe. Scanning1024 positions does not expand the qualified context-ID domain0..127. Sampler unloaded. This is a register/snapshot observation, not proof of table ownership, GPU coherence or successful translation.

The kernel ring wrapped during register capture, so the initial prefix-only log comparison asserted after all reads and cleanup. Recovered the completed attempt using a unique exact32-line overlap with the previous log tail, then checked all13 ordered address/value records and module absence. No second hardware run occurred. Reusable harness now handles this overlap; before/after logs preserved.

Next prepare an explicit context-insertion/removal trial in the empty reserved table while preserving loader MMU base/configuration. Verify idle GPU/firmware state, existing entry zero, cache clean/ordering/invalidation and mandatory restoration before freeing owned device tables. Before publishing a drawing job, replace context/shader/target/parameter/event/queue fixtures. This boot remains usable; no reboot or macOS required by these reads.

Evidence2026-10-08-live-mmu-state.json/-dmesg.txt and2026-10-08-loader-gptbat-state.json. Exact module source and full captured ADT/logs/table snapshot included in return build/mmu-state-read andbuild/loader-gptbat-sample. No Apple instruction bytes.
