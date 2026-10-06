# T6040 SME trial

Enable upstream arm64 SME/SME2 support alongside the native-tested shallow
saved-WFI path. No Apple control-register changes or invented capabilities.
Hardware and firmware exposure remain a native test question.

`PROBE` reads HWCAP2 and PR_SME_GET_VL before instruction tests. Upstream Linux
arm64 FP selftests cover ZA, SME2 ZT and streaming vectors across context switches.
The sleep variants replace sched_yield with nanosleep to exercise idle gaps;
syscalls preserve ZA/ZT but clear streaming mode by design. They do not prove
all architectural state, TPIDR2, deep idle, suspend or hotplug correctness.

`run.py` runs paired workers on every CPU with idle disabled, then enabled.
It requires nonzero iterations and a clean exit, captures idle progress and
journals, and disables the opt-in on a detected failure. A hang cannot run cleanup.
The native agent must verify per-core return growth before claiming idle coverage.

The separate `7.1.3-m4rch-sme` module tree is embedded in the trial initramfs,
verified and installed into a new directory before systemd. Installed pacman
modules and normal boot artifacts are untouched. This temporary tree is not a
pacman package; native promotion must package the tested kernel properly.

Original helpers are MIT. Upstream assembly selftests are GPL-2.0-only, from
Linux commit e9d2237cd064e6d086d938cd9c85e0c963cf7291,
`tools/testing/selftests/arm64/fp/` (Asahi-derived pinned source).

Linux SME ABI: https://www.kernel.org/doc/html/next/arch/arm64/sme.html
