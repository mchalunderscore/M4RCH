# Installation and maintenance

The running J614s system booted the source-built forked kernel, Aura and U-Boot in a one-shot trial; this kernel is now the persistent GRUB default. See [status](status.md) and [recovery](recovery.md).

Use the [Aurora update workflow](aurora-update-workflow.md) to review and build updates. The standard stage-two updater is enabled and includes the installed kernel's device trees, including J614s. Aura, U-Boot, the device tree, kernel and initramfs form a coordinated boot setup.

The machine-specific Wi-Fi and other vendor firmware are private and are not provided by this repository. Internal speakers remain disabled pending J614s-specific protection and qualification. The installed graphical sudo bridge and its rollback are documented in [its package](../packages/dozor-sudo-m4rch/README.md).

Before changing boot components, read [recovery](recovery.md), verify the relevant partitions and backups, and preserve a known-working loader and matching kernel. Existing recovery copies are on the same disk and do not protect against disk failure.
