# Native-command trial installed for the next user boot

The distinct `7.1.13-m4rch-gpu-native-reset` kernel and retained owner are built,
independently reviewed, installed additively, and selected as default5. All six
GRUB entries remain available. No reboot, live GPU operation or module load was
performed during installation. The current boot remains the stopped, sealed v1
instance `ce6572c9-2491-4c87-8e27-6e82cc0ac657`, with all174 pages retained.
The native-command trial has not run and its boot behavior is not yet tested.

The v1 checked command stopped while requiring DEV_DISABLE10 to read set; it
never asserted RESET31. Matched Apple PMGR evidence instead delivers forced
full-word `B|0x400`, `B|0x80000400`, minimum1us delay, and `B` commands without
requiring those command bits to latch. The separate native probe tests that
specific hypothesis with exact command attempts, desired words, write errors,
read-stage counts/errors and policy observations. Native AUTO handling and
conditional T6041 register-wrapper side effects remain qualification gaps.
Command delivery does not establish physical reset coverage or memory retirement.

## Qualified candidate

Candidate: `out/gfx-native-reset-owner/candidate`.
Build receipt SHA256 `96d5dda793adf700017b5e28b33b2ee6e2964ab058a08ec4bcdcdf68fbe7909e`.
Owner SHA256 `51aeeab15ff4a369ce11717e24d7ba6507c176981eedfa3da61747b47959e432`.
Kernel qualification SHA256 `133370f18dc105e7fe310c4945073ad49b64b480e4ca828ced63289a7e34e0d2`.
Running notes required after reboot:
`85c56f7a3d7409747dd67fe1dcbf8839562aafab16a9124f9304689a14de437d`.
Build ID `16d77884e7ddc1bad8a7e6588fab2009e8c85e1e`.

All eight helpers match the new release. Actual owner imports resolve to
`apple_pmgr_t6040_gfx_native_probe` and snapshot, with no checked-pulse import.
All10 artifact/15 owner-source pins match. Graph `287f2c53...` and triangle
backing `35112ef3...` are unchanged. The exact version2 receipt derives startup
parameters `run_gate=2 observe_ms=5000 resident_session=1`; mandatory gate1 shadow
still precedes publication. Shutdown, release, work submission and warm restart
are excluded. Native API396 actual-C ASan/UBSan cases, owner517 cases and wrapper54
checks passed; independent reviews distinguish software guards from hardware proof.

The full W=1 kernel/module build passed with192 modules, preserving the original
tree, v1 artifacts and protected installed files. Only reviewed PMGR and the
previously promoted fixed-host USB source differ from the maintained baseline;
configuration differs only by release suffix. The new initramfs preserves root
geometry and early USB preload and contains five exact new-release module bodies.
The independent closure verifies all52 final receipt artifacts and208 module-root
regular files without symlinks or executing init code.

## Installed boot state

Exact additive receipt SHA256:
`1fba6d2d38b76b163673cf276eed0426b9b13679231e6649d691abde6676f197`.
New boot directory `/boot/GFXN001`; module directory
`/usr/lib/modules/7.1.13-m4rch-gpu-native-reset`.
Image SHA256 `b6831d75dfa0c84c1fb2ecb120027d6202ce7347b860466a68d4eb58c54f1093`.
Initramfs SHA256 `b0831ca98d38f6419fa1bcfa22248d514c34af5cd9646d92c43753b33e2919a5`.

Installation staged and verified new paths before appending index5 while keeping
default4. The separately reviewed selector then backed up that exact six-entry
menu and changed only default4 to5, following the user's requested default because
GRUB input is unavailable. Final GRUB SHA256:
`0ec2ace33d48d701930d03f869b2a67127421fdeebab55a0968e132aa65193cb`.
Backup: `/boot/GFXN001/grub-installed-default4.cfg`; the original five-entry menu
is also saved as `/boot/GFXN001/grub-before.cfg`. Both operations returned complete
and rechecked payloads, installed module tree and protected files. No package
hooks, remount, EFI rebuild, hardware operation or reboot occurred.

Post-install read-only checks confirm the old running kernel/notes/boot, retained
GPU owner refcount1, all three SPMI PD bindings and all three USB role providers.
The corrected v1 initramfs/module remain intact. The companion JSON pins these
results and the independent review leaves.

## Next native boundary

After the user's reboot, root must match the new notes/release/receipt and USB
bindings before running the prepared owner once. Sample and take a read-only GFX
snapshot; admit at most one typed `gfx-reset` under its exact no-work/pinned-power
conditions. Interpret version2 per-command/per-read provenance and compare ASC
and already-qualified firmware-owned shared observations. Then retain backing
and perform only sample, read-only snapshot or packet-free stop.

No outcome permits another reset, previous failed warm wakes, new graph, firmware
restart, unload, PM release, unmap or free. Frozen host journal data and the V6
idle predicate do not establish DMA cessation. Recovery, fresh execution,
completions and changed target pixels remain separate unproved steps. The full
GPU/Mesa/DCP desktop goal is active and incomplete.
