# Packages and source records

The current J614s installation uses packages built from the Aurora ALARM fork and selected Aurora packages. See [current status](../docs/status.md) and the [update workflow](../docs/aurora-update-workflow.md).

- `linux-m4rch/`, `m1n1-m4rch/` and `u-boot-m4rch/` retain older packaging and source references used in hardware investigation notes. They do not describe the current boot stack.
- `mesa-m4rch/` retains earlier build inputs; it is not the installed Aurora fork recipe.

The native `make` workflow repackages retained older boot artifacts or builds the pinned Mesa source; it does not build the current kernel and loader stack. See [boot recovery](../docs/recovery.md) before changing those components. Superseded staging recipes and their notes are in Git at `dc600bb`.
