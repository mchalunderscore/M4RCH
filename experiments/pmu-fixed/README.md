# M4 fixed-counter trial

Optional temporary module for the exact J614s `7.1.3-m4rch` kernel. It does
not register a perf PMU, enable an interrupt, change the DT/boot chain, select
programmable events, or expose counters/configuration to unprivileged code.

Loading creates a root-only debugfs file. One read runs three scalar dependent
loops (256/4096/65536 iterations) on the selected online CPU. It reads fixed
PMC0 cycles and PMC1 instructions, enables only those counters and their EL1
filters temporarily, and restores/reads back original PMCR0/1. Counter values
advance and are NOT rewound. Reads/writes use existing Linux register names;
no arbitrary address/selector, counter reset, thermal or clock control exists.
Any enabled counter, interrupt enable or pending interrupt refuses the trial.
Each loop has three instructions per iteration; the parser checks counts with
limited overhead allowance. Local interrupts are masked during the short test.

This is hardware-unverified. An unexpected system-register trap or wedged
hardware cannot be recovered by a userspace timeout. Exact board/MIDR/ABI
checks reduce accidental scope; they do not prove hardware access. Do not
force-load, autoload or repeatedly retry a failure. Save work before the trial.
The two-millisecond timing check stops further loops after a slow observation;
it is not an interruptible watchdog or a bound on a faulting instruction.

## Native use

Use the delivered `HANDOVER.md`, first recording raw SMC/boot state. Run one
CPU at a time through the wrapper. Stop after ANY failure and return the raw
capture/journal instead of altering permissions, PMU state or kernel policy.
It checks hashes, GNU build ID/module provenance, online M4 MIDR and apparent
ownership. Cleanup unloads the module; no reboot/enrollment is normally needed.

Successful counts would support a later count-only perf implementation.
Clock estimates cover short CPU-wide EL1 work and read/barrier overhead, not
per-task accounting, maximum boost qualification or calibrated frequency.
Cache/branch events, overflow IRQs and standard perf integration remain future
work. No DT compatible is borrowed from M1/M2.

## Sources and provenance

Original experiment code is MIT or GPL-2.0-only; Linux register header remains
GPL. Public hardware facts cross-checked against:

- Linux `arch/arm64/include/asm/apple_m1_pmu.h` and Apple PMU driver.
- Apple's published XNU `osfmk/arm64/monotonic_arm64.c`: fixed registers,
  counter widths, enable bits and execution-mode filters. No XNU code copied.
- Installed `/usr/share/kpep/cpu_100000c_2_17d5b93a.plist`: fixed0/1 aliases.

https://github.com/torvalds/linux/blob/master/arch/arm64/include/asm/apple_m1_pmu.h
https://github.com/apple-oss-distributions/xnu/blob/main/osfmk/arm64/monotonic_arm64.c

The fan research cited in HANDOVER has separate proprietary-binary provenance
and was not used to implement this counter experiment.
