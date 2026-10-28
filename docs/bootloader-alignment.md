# Historical Gravity bootloader alignment

The old Gravity stage-two alignment and its trial collector were superseded by
the current m1n1/U-Boot stack. The full investigation and collector are
available at `173c1dc`:

```sh
git show 173c1dc:docs/bootloader-alignment.md
git show 173c1dc:tools/boot/collect-alignment.sh
```

See the [current bootloader comparison](boot-upstream-comparison.md) and
[maintenance inventory](installation-maintenance.md) before considering a
loader change.
