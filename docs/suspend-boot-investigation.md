# Suspend and wake

The normal J614s entry uses `mem_sleep_default=s2idle`. Lid-close suspend and
wake passed on AC and battery. The owner also reported normal lid wake during
the driver-autoload trial; a USB-C TV returned from one sleep before that
autoload change. Power-saver remained active and its CPU caps were restored
after an attended sleep. Hibernation and hybrid sleep remain disabled.

The machine has no verified automatic wake timer; an unsuccessful wake may
require a power-button reset. External displays have not yet been retested
under the permanent autoload setup. See [installation and maintenance](installation-maintenance.md)
for the boot chain and recovery limitations.

The promoted kernel already contains DCP resume machinery related to Aurora
[#313](https://github.com/aurora-silicon/linux/pull/313). Aurora's
[T6040 idle work](https://github.com/aurora-silicon/linux/pull/371) and
[J616s display work](https://github.com/aurora-silicon/linux/pull/451) informed
the investigation but do not independently qualify this J614s configuration.
The detailed trial record is available with
`git show e7baa0e:docs/suspend-boot-investigation.md`.
