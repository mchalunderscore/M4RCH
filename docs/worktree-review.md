# Worktree and local artifacts

The active tree contains the package recipes, source records, maintenance
notes and tests for the current J614s installation, along with older builder
code that still needs a separate dependency and recovery review. Historical
SD-card workflows and completed trial code have been retired. The previous
review, including its original grouping, is preserved in
`out/documentation-before-condensing-20261028.tar.gz`.

Important limitations for reviewing or publishing this tree:

- The U-Boot source record contains this installation's ESP UUID. The speaker
  assessment and saved audit include unit-specific calibration values. Review
  machine-specific material before publishing.
- Git does not include ignored `out/` build inputs, firmware, private hardware
  captures or the preserved historical archives. The package preparation
  script still uses promotion artifacts there. Keep independent copies of
  required inputs; do not treat a source commit as a complete system backup.
- `make packages` and its validator are not qualified for the current installed
  stack. See [maintenance](installation-maintenance.md) and the
  [package guide](../packages/README.md).
- External displays under driver autoload and the headphone jack still await
  hardware tests. Speakers remain disabled.

`python tools/worktree-inventory.py` groups the current Git status for review;
it is read-only. `make check` validates the retained source tests, while
standalone graphics regression tests may require a separately supplied source
tree.
