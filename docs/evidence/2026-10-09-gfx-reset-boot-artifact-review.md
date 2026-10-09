# GFX reset boot artifacts: independent review

2026-10-09. **No remaining code or artifact blocker** on frozen artifact receipt `7a906c7dceb97972c1e7316c1736e2a9e2aa5444c960923026ceef36c4c38178` and installer `e9fcd5778c4787553fc1d7b8da818a5c2e8acb30f925c52aa65c0dcb91aa2641`. This review performed no installation, mount/remount, module load, GPU operation or reboot. A writable, identity-matched `/boot` is a separate execution prerequisite; the reviewed installer refuses a read-only mount.

The existing boot configuration has four entries and default index 1. The proposed fifth entry is `7.1.13-m4rch-gpu-reset (GFXR001 checked reset trial)` at index 4, using `/GFXR001/vmlinuz` and `/GFXR001/initramfs.img`. Its complete menu retains the exact 1398-byte original prefix and default 1, including both guarded GPU and USBR001 backup entries. The new entry retains `asahi_m4.probe_only=1`; it does not become the default.

Generic hooks must be bypassed. Installed `90-mkinitcpio-install.hook` can select all presets when initcpio inputs change. `99-m4rch-boot-update.hook` invokes an updater that replaces normal kernel/initramfs, board DTBO, GRUB and EFI files from the stale two-entry 7.1.3/default0 template. The proposed path uses a prebuilt workspace initramfs with explicit `--nopost`, module root, hook directory, build directory and output, and invokes no package transaction, generic updater or EFI generation.

The independent artifact audit verified all 192 module copies against qualified staging and the Image against the compiled reset kernel. The full module tree has no symlinks and uses only the new release/pkgbase. In-memory early-newc plus gzip parsing verified the actual `/init`, new release configuration and five NVMe/SART/USB module payload hashes. The only runtime init change is the new pkgbase check: root UUID, partition identity, geometry, NVMe handling and the early `dwc3_apple` preload before `switch_root` remain intact. Sixteen protected host hashes matched the saved preinstallation snapshot.

The final combined installer audit verified:

- One receipt byte string supplies both the caller-bound SHA and decoded JSON. Every artifact record, module manifest, compiled identity and selectable menu title is internally consistent.
- Cached before/after/entry bytes and each boot payload are read against fixed reviewed size/hash records. Staged and published boot files are checked against those same records, and module trees are checked against the exact fixed file set and hashes.
- Execution uses the updater's common lock, verifies root and FAT UUID/PARTUUID plus writable FAT, rejects preexisting final/partial paths, checks space and stages only the new release and isolated GFXR001 paths.
- Modules and boot files are verified before publication and synced before the existing GRUB file is replaced. Protected host files and the original menu text are checked again immediately before that replacement; the staged menu is syntax checked and its published bytes are verified.
- A partial failure records progress and retains only newly created paths for inspection. The script does not delete prior boot/module paths, change the default, mount filesystems, run package hooks, regenerate EFI, load modules or reboot. Default audit returns before mutation and mount probing.

The review resolved a fixed-hash staging gap: comparing a staged file to the current mutable source could accept an artifact changed since review. Fixed expected records now cover kernel/initramfs copies, the receipt decode and cached menu bytes. Independent final default audit and `grub-script-check` passed. This establishes artifact/control consistency, not a successful boot, power-loss recovery or physical GPU reset/recovery result.

The companion JSON binds frozen inputs, saved dangerous-hook source snapshots and the independent in-memory archive audit. Protected host observations describe the state before any separately authorized installation; the review did not reread live GRUB once that separate installation began.
