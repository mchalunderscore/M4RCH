# Linux integration point for native GFX shutdown coordination

The installed Gravity-derived PMGR provider has no PMP or PMC coordination in
its normal OFF callback. `apple_pmgr_ps_power_off()` calls
`apple_pmgr_ps_set(0,false)`; that function writes TARGET0 and polls ACTUAL0
(`out/gfx-native-reset-kernel/linux/drivers/pmdomain/apple/pmgr-pwrstate.c:517`,
`:609`). BUSY-clear and native notifications are not part of that callback.
Its domains use `GENPD_FLAG_IRQ_SAFE` (`:732`), so inserting the native long ACK
wait inside this callback would put the wait under an atomic genpd lock.

A distinct retained owner can coordinate before its sole PM put without
rebuilding the kernel. The current candidate's `recovery_command_store()`
(`asc-graph-init/recovery-cycle.h:238`) runs in sleepable sysfs context under
`graph_io_lock`. `gfx_poweroff_attempt()` (`gfx-reset-scope.h:197`) seals the
receive worker, checks all retained no-work/STOP/ACTIVE/usage1 prerequisites,
and only then clears `held` and calls PM put (`:223`). Insert a separately
qualified coordination core between those checks and the PM put. Keep the
attempted candidate unchanged.

`CONFIG_APPLE_PMP_REPORT=y` does not provide the missing callable interface.
`drivers/pmdomain/apple/pmp-report.c:56` matches only t6000/t6020/t8112, uses
STATUS mask1 and different dashboard offsets, and registers separate genpd
providers. No Apple PMC implementation exists in the reviewed Apple driver
subtrees. `CONFIG_APPLE_PMP` is disabled; `drivers/soc/apple/pmp.rs:402` matches
t6000 and starts/patches an ASC/RTKit firmware service. Enabling or invoking
that driver would introduce firmware startup work unrelated to this retained
notification trial.

The saved 2026-10-07 FDT contains no functional PMP/PMC compatible node and no
direct `/soc` resource overlap with the native lead's PMP5003c0000/30000 and
PMC504000000/1000000 regions. Its pmp@410 and pmc@120 labels under PMGR502800000
are always-on power state nodes, not dashboard/voter resource providers. The
current trial's saved genpd summary also labels PMP/PMC ON. These observations
are not a current-boot FDT/resource-ownership proof; fresh-boot qualification
must repeat metadata-only ownership checks before any future mapping/write.

Reserve the authoritative PMP and PMC resource spans exclusively and retain
the mappings through the terminal outcome. Scan available OF MMIO resources
and platform bindings for aliases and reject conflicts. Successful
`request_mem_region()` alone is insufficient: the reviewed syscon path
(`drivers/mfd/syscon.c:58`) and CPU frequency path
(`drivers/cpufreq/apple-soc-cpufreq.c:337`) map through `of_iomap()` without
claiming a busy region. The historical FDT has identity `/soc` ranges and no
matching direct resources, but no current absence is inferred from that.
Do not initialize, start or wake PMP, initialize PMC, or synthesize compatible
DT nodes to make this experiment run.

The exact native sequence remains a dependency on the mapper agent's frozen
coordination evidence. Its current lead selects a PMP64-bit request clear at
base+10f00 preserving all bits except13, followed by the corresponding ACK
payload and raw-status check, then type2 GFX PMC voter clears of mask4 across
three rails, before the physical target0 transition. Read payload and raw
status as separate QWords: REQ1e00/1e08, STATUS10/18, ACK1e80/1e88. This review
has not independently decompiled those addresses. Native mode2 is an
initialized host object field, not a qualified hardware mode register; no
runtime dashboard equivalent is established. STATUS payload0's native ACK
skip is not proof of safe inactivity. Native OFF does not require the old
REQ13 bit set; already-clear votes must be recorded as no change.

The future owner should log before values, desired masked values, attempts,
read validity/errors and ACK observations before its single PM put. Refuse
before that put if setup, selected encoding, required ACK, PMC write or
readback is missing. Seal the terminal coordination gate before first intent,
keep all174 pages/context/consumer/module and every mapping pinned on any
result, and retain a still-held PM reference on pre-put refusal. No retry,
rollback or compensating get/put follows. Retain the strict OFF predicate and
post-OFF ban on ASC/SGX/mailbox access. A successful vote write or ACK alone is
not whole-GPU cessation, DMA drain, restart or backing retirement.

This pair is an offline implementation recommendation, with17 input file
hashes and saved-FDT findings. No hardware, privileged action or source change
was performed. The old current owner remains diagnostic-only.
