# Native telemetry mapping recovery candidate

Prepared candidate: `out/gpc-telemetry-recovery/candidate`.
Module SHA256:
`0c7c32b00592aa0d42a2a96313e26fe87a426175f03b17739a125ecb5bfd8f3d`.
Historical preparation record: this candidate ran on bootf5f3a7cc.
See `2026-10-09-gpc-telemetry-recovery-live.md`; do not repeat unchanged.

The preceding live trial passed engine-on and then crashed while reporting the
transition through a null PushTelemetryDashboard mapping. This candidate adds
the native slot9 descriptor and one writable 16 KiB device page:
PA `5003d0000`, firmware VA `fffffc2001b10000`. The callback subtracts `10000`
from its selector and writes offsets `f98/f9c`; its whole access fits this page.
The descriptor uses the same qualified experimental platform flags as slot11;
native CPU HAL flags are not assumed equivalent to firmware descriptor flags.

Exactly 11 graph bytes change, all within the previously zero slot9 descriptor.
The header and receipt now contain 101 MMIO leaves and 170 graph mappings.
Both loader allowlists admit only the added exact physical/virtual pair.
All 174 owned pages, auxiliary clocks, GPC policy, epoch pointer, native masks,
immutable triangle/shaders/commands and completion backing are preserved.
The runner also checks fresh CS/AFR ADT property hashes and the GPC board guards
before publishing any root.

The immediate return path uses already-present primary/PRC mappings. No further
mandatory missing mapping was found there. Adjacent slot10 is a distinct read
space with conditional later consumers; this evidence does not establish that
it is required on the present continuation.

Validation: `W=1` module build, all source/artifact receipts, exact graph delta,
unchanged draw backing, 20 existing mapping tests, Python syntax and diff checks
pass. The firmware callback replay proves its two stores against emulator RAM,
not physical telemetry behavior or complete startup.

After a fresh normal reboot and clean preflight, run once:

```sh
sudo -n python experiments/t6040-gpu/run-root-envelope.py out/gpc-telemetry-recovery/candidate --graph --run
```

If both idle recovery cycles finish and consume fresh controls, run another
typed `recover` on that same retained instance, then submit its one immutable
triangle. Submission captures completion and pixel evidence at 1/5/15/30 seconds.
No subsequent publication or recovery is allowed after that batch. Failed
diagnostic sessions permit only sample/stop; a crashed stopped session permits
neither recovery nor submission. Every outcome retains backing until reboot.
