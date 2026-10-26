# Additive native-command trial boot

The previous checked-pulse hardware trial timed out waiting for DEV_DISABLE10
to read set before it ever asserted RESET31. Matched Apple PMGR evidence uses
forced full-word commands and a minimum delay without requiring those command
bits to latch. The separate `7.1.13-m4rch-gpu-native-reset` kernel adds that
experimental probe, preserves the legacy API, and includes the validated
fixed-host USB source correction. Command delivery still does not establish
physical reset coverage, DMA retirement, recovery, or rendered pixels.

`install-additive.py` audits by default. Copy it alongside the finalized
`out/gfx-native-reset-install/artifact-receipt.json` and all pinned inputs. Its
explicit root execution verifies the exact receipt, original boot/root geometry,
protected installed files, and all new module and boot payloads. It installs only
new release/module and `/boot/GFXN001` paths, then appends the sixth GRUB entry
after verifying those payloads. Existing menu text is an exact prefix and default4
is preserved. It invokes no package hooks, remount, live module operation or
reboot. A partial result requires inspection, not an automatic repeat.

`select-default.py` also audits by default, and can run only after the exact
reviewed additive installation completed. Its separate root execution changes
only `set default=4` to `set default=5`, preserving all six entries and an exact
backup under `/boot/GFXN001`. The user requested the trial as default because
GRUB input is unavailable. Neither script boots the machine.

After the user's next boot, match the running kernel notes, new release,
qualified candidate and USB bindings before any trial. Use the mandatory gate1
allocation shadow and gate2 retained owner. The typed native `gfx-reset` consumes
one permanent attempt and retains all174 pages on every outcome. Afterward only
bounded sample, read-only `gfx-snapshot`, and packet-free stop are admitted. Do
not retry the reset or the previous failed warm wakes, restart firmware, unload,
release PM ownership, unmap, or free backing. The version2 outcome decision
evidence defines how to interpret command and read provenance.
