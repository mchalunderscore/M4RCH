# Historical Apple boot-stub upgrade

The earlier Apple-stub upgrade and its target-specific Recovery helper belonged
to a retired installation workflow. They are not a verified recovery procedure
for the current setup. The full guide and helper remain in Git at `173c1dc`:

```sh
git show 173c1dc:docs/stub-upgrade.md
git show 173c1dc:tools/boot/repair-stub-policy.sh
```

The current boot chain and its recovery limitations are documented in
[installation and maintenance](installation-maintenance.md). Kernel and Mesa
updates do not by themselves require replacing the Apple stub.
