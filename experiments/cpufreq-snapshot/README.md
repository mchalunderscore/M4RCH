# Driver-owned clock snapshots

`experimental-cpufreq-snapshot.patch` adds root-only JSON snapshots to the
existing Apple cpufreq driver. It reads the already mapped 64-bit command
register at 0x20 and, only for known status layouts, the 32-bit status at 0x50.
Each read has boottime brackets. Selected compatible, masks/shifts, immutable
initial CPU membership, OPP levels, command/status frequencies and the sampled
policy frequency make request handling and state decoding inspectable.
Readings are successive, not atomic; neither is a physical clock measurement.

Protected debugfs file operations pin active reads. Policy exit removes/drains
the interfaces before releasing the frequency table, MMIO mapping or private
data. The show callback takes no policy or hotplug lock that exit might own.
No worker, control writes, register scans, DT change or persistent service.

Use the generated kit and `HANDOVER.md`. The default capture reads three
policies for 60 samples. `--probe-on-boost` optionally brackets one previously
accepted fixed-counter probe per P cluster, only when a high command is
observed. It changes fixed-counter enable/filter bits temporarily, restores
them, and unloads the module. It does not inject workload or force a clock.
Signals request cleanup after bounded reads. A userspace timeout cannot recover
a kernel/MMIO fault; failed cleanup stops without an automatic retry.

`check-format.py SOURCE` compiles the actual kernel formatter against synthetic
MMIO and passes its output through the capture parser. This validates format,
decoding, fallback and aperture selection, not hardware or teardown behavior.

The exact source and module build receipts, matched pacman kit and accepted
rollback travel together. Kernel release remains `7.1.3-m4rch`; GNU build ID
and payload hashes distinguish generations. No native acceptance or speedup
is claimed before the return. Kernel-derived patch retains GPL-2.0-only.
