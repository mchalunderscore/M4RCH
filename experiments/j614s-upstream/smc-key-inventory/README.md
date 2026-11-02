# J614s SMC and thermal observation

Findings, limits and upstream references: [investigation report](../../../docs/j614s-smc-thermal-investigation.md).

`smc_inventory.c` is a temporary diagnostic module for the booted J614s kernel.
Its `keys` debugfs file enumerates metadata through the kernel's existing SMC
interfaces without reading arbitrary values. `samples` reads a fixed list of
otherwise unexposed T/P float keys only after checking their metadata. `fan_modes`
reads the two fan-mode keys with the same operation used by the existing
macsmc driver. `qos` reports the cpufreq user requests separately from effective
limits. It exposes no SMC write operation. The root-only results go under
`/var/lib/m4rch/j614s-smc-thermal-20261102`, never into the public repository.

`guarded_load.py` records actual hardware activity and uses independent CPU/GPU
thermal-zone limits plus `TVMR` and `TVMr` cutoffs. Its worker processes have a
parent-death signal and finite deadline. `frequency_sweep.py`,
`compare_governor.py` and `multicore_budget.py` temporarily change frequency
requests and/or GPU-zone governors for controlled comparisons and restore their
original values on exit. They are research helpers, not boot-time policy or an
installation package. User settings, governor identity and available sensors
must be checked before reusing them; do not use the helpers for unguarded stress
or assume the experimental limits are qualified hardware limits.

The retired sensor-table experiment was boot-tested on the installed PR-stack tree: all
four added keys and the 24 existing CPU/GPU thermal zones were readable. The
exact standalone #795 branch was not separately booted. The added keys have
generic labels because their physical meanings are unconfirmed. The normal
loader has been restored for the next boot, and a recovery copy remains at
`/boot/efi/m1n1/boot.bin.m4rch-before-smc-sensors`.
