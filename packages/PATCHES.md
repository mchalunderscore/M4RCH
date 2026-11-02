# Patch organization

Package patch files include upstream changes, submitted proposals and older source records. A patch's presence does not mean it is installed. See [current status](../docs/status.md) for the current boot components and the [update workflow](../docs/aurora-update-workflow.md) for reviewing replacements.

The older `linux-m4rch`, `m1n1-m4rch` and `u-boot-m4rch` recipes repackage retained binaries. Their ordered source records and checksums support the installer and staging tools, but do not establish reproducible builds. Their source series are not a description of the current upstream-based boot stack. Firmware, build inputs and recovery artifacts remain machine-local.
