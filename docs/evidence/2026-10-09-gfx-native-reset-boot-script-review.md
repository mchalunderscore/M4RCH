# Native boot scripts: compact source review

2026-10-09. This records the completed read-only review after the two selector guard fixes. No further audits, tests, hardware operations, or source changes were performed to save this note. Artifact closure, installation and default selection were pending at review completion.

The reviewed sources are:

| File | SHA256 |
|---|---|
| `install-additive.py` | `eb330038069b056c0ced70421322371c49ba86229d74bfb936cfa30f4b0ebaed` |
| `select-default.py` | `9249316b91c433996dc016ea11487a097b7fa66de3be71048d2faaf1e439b6d8` |
| `finalize-artifacts.py` | `ca0a8ccbd55530ed5b52eba6db2c52345ce7cb174847c459e03a4bb951c40ef3` |
| `README.md` | `9860fdba7682d86a4558c0feb5fd61a8d6160a10b257c21264b067ea8aeeec29` |

No source-review blocker remained. The additive installer retains the exact existing five-entry menu as a prefix and preserves default4. It refuses existing new target/staging paths, verifies new module and boot payloads, then publishes the sixth entry under the normal updater lock after staging, hash checks and GRUB syntax validation. Protected host inputs are rechecked around publication, and partial operations retain progress records for inspection.

The selector requires the exact reviewed artifact receipt and completed matching additive-install result. Its unique enrolled installer record, non-symlink path, size and hash are verified before executable import. Installed native modules, boot payloads, protected files and the exact six-entry/default4 menu are verified before and under the lock, immediately before publication, and afterward. The only menu edit replaces the single default4 assignment with default5; an exact default4 backup and a syntax-checked staging file precede atomic publication. This persists the user's requested boot choice while GRUB input is unavailable and keeps all six entries.

The finalizer closes the owner/kernel/source artifact pins, binds the installer and selector, constructs the additive menu in its work destination, syntax-checks it and runs the installer's audit. Its source review did not establish actual final artifact readiness.

No package-hook, mount/remount, live-module, GPU or reboot operation was found in these reviewed scripts. Caller preparation of a writable boot mount is separate. Source review does not confirm installation, selection, bootability on hardware, or GPU reset/retirement behavior. Both initially identified gaps were fixed before this review was cleared: installer validation before import and installed native module-tree verification during default selection.
