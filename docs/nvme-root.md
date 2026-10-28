# Historical SD-to-NVMe migration

The original one-time migration moved the SD installation to the internal NVMe
using a specific reservation and disk layout. It is complete and its kit is not
a recovery procedure for the current system. The original guide and migration
sources remain available in Git at `bce491f`:

```sh
git show bce491f:docs/nvme-root.md
git ls-tree -r --name-only bce491f -- tools/nvme
```

For the current boot layout and recovery context, see the
[maintenance inventory](installation-maintenance.md) and
[external-display promotion record](external-display-investigation.md).
Do not apply the old partitioning instructions to the current disk.
