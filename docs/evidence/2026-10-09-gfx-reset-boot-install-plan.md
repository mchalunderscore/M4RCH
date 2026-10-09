# Additive boot artifacts for the checked GFX reset trial

Prepared workspace artifacts are at `out/gfx-reset-install/`. The separate
`7.1.13-m4rch-gpu-reset` kernel, matching module tree and isolated NVMe initramfs
are ready for root's reviewed additive installation. This preparation performed
no host installation, boot edit, mount/remount, module load, GPU operation or
reboot. A later root-owned installation has its own `install-result.json`.

Reviewed artifact receipt SHA256:
`7a906c7dceb97972c1e7316c1736e2a9e2aa5444c960923026ceef36c4c38178`.

Draft installer SHA256:
`e9fcd5778c4787553fc1d7b8da818a5c2e8acb30f925c52aa65c0dcb91aa2641`.

## Existing boot contract

The current GRUB configuration is a hand-maintained 1,398-byte file with four
entries and `set default=1`. Existing entries are maintained Gravity, guarded
GPUC001 contract, Gravity with peripherals disabled, and the USBR001 backup.
The draft preserves that complete file as an exact prefix and appends entry 4:
`7.1.13-m4rch-gpu-reset (GFXR001 checked reset trial)`. Default 1 remains unchanged.

The existing ESP uses FAT UUID `33CE-1F10`, partition UUID
`5fdb35c6-3a66-416d-8358-6555fd99fcc5`, and is mounted at `/boot`. Root identified
it as `/dev/nvme0n1p3`. The initial `ro,nosuid,nodev` observation was the
restricted sandbox bind view, not the native mount policy. Root later verified
the native vfat mount was already writable and preserved that state without
remounting; APFS remained unmounted. See `out/gfx-reset-install/root-mount-policy.json`
(SHA256 `e986ac52439a46d5fb2a263ec33cabc3687310da2053f6ff9a2b1aacf459539f`).
The installer never mounts/remounts; root must preserve the native prior mode
when arranging a separately necessary write period.

The new entry loads `/GFXR001/vmlinuz` and `/GFXR001/initramfs.img` with the same
NVMe root and tested arguments as the guarded entry:

```text
root=UUID=7568fe83-378f-5b78-ab12-ccc36ff09a90 rw console=ttydc0 console=tty0 rdinit=/init idle=nop arm64.nowfxt pd_ignore_unused clk_ignore_unused asahi_m4.probe_only=1
```

No new stage-two loader, EFI application, board overlay or bootloader enrollment
is needed. Existing `boot.bin`, `EFI/BOOT/BOOTAA64.EFI`, board.dtbo, main kernel
and initramfs, GPUC001 and USBR001 images remain protected. The installer verifies
16 recorded host file hashes before staging and before menu publication. The
old GRUB prefix is saved as `/boot/GFXR001/grub-before.cfg` by the future installer.

## Kernel, modules and early userspace

Kernel qualification remains
`out/gfx-reset-kernel/kernel-qualification.json`, SHA256
`47e6e5c9027da74d3b98b4877415f24cd393baf2858c9567d73da2f31e0ec95b`.
Image SHA256 is `39f25240a6d4ccfdea340c1c8a88915c22e6997b30d1146e3bbba88868a7cbba`. Source, PD/USB changes and guarded GPU
policy were preserved as recorded in the kernel-candidate evidence.

The installer adds only the new release directory
`/usr/lib/modules/7.1.13-m4rch-gpu-reset`. Its 208 regular files include all 192
qualified modules, dependency indexes, `vmlinuz` and pkgbase
`linux-m4rch-gpu-reset`; there are no source/build symlinks. This is a direct
experimental installation, with an explicit receipt, rather than a pacman-owned
kernel package. Existing release directories, services, blacklists and normal
`/usr/lib/m4rch/kernel-release` stay unchanged. Existing services use ordinary
`modprobe`, which selects modules for the running kernel release.

The isolated initramfs clones the installed GPU-contract init and hook. The init
changes only the pkgbase comparison to `linux-m4rch-gpu-reset`; the hook changes
only its source init path to the workspace clone. This retains the qualified
`modprobe dwc3_apple` immediately before root udev/switch_root. The generic
`/usr/lib/m4rch/init-nvme` lacks this step and is not a replacement.

The generated `/etc/nvme-root.conf` exactly equals the installed boot.conf plus
`KERNEL_RELEASE='7.1.13-m4rch-gpu-reset'`. Root UUID, partition UUID
`e80ee324-c4c5-4f3e-81b7-464adb71d41a`, byte offset 363598970880 and extent 126880841728
remain unchanged. Actual image extraction confirmed exact init/config bytes,
new-release module paths and all five matching early module payloads:

- `apple-sart.ko`, `nvme-core.ko`, `nvme-apple.ko`
- `dwc3.ko`, `dwc3-apple.ko`

The hook includes busybox applets, required disk/filesystem tools, modprobe,
existing peripheral firmware and regulatory databases. Ext4, JBD2, mbcache,
DART, mailbox, RTKit and PMGR prerequisites are built into the qualified kernel.
No GPU resident owner or reset command is embedded or automatically invoked.

Initramfs SHA256:
`21343273658f7bef4d0e1e335408ac73f6c5eea5e3c34f183874617bcd8dbdda` (14687815 bytes).

## Generation and package-hook audit

The isolated image was built without sudo, using only workspace output paths:

```sh
mkinitcpio --nopost -k 7.1.13-m4rch-gpu-reset \
  -r /home/alice/Desktop/m4rch/out/gfx-reset-install/module-root \
  -D /home/alice/Desktop/m4rch/out/gfx-reset-install/hookdir \
  -c /home/alice/Desktop/m4rch/out/gfx-reset-install/mkinitcpio.conf \
  -t /home/alice/Desktop/m4rch/out/gfx-reset-install/tmp \
  -g /home/alice/Desktop/m4rch/out/gfx-reset-install/initramfs.img
```

Post hooks are disabled; no host hook, config or preset is installed. Current
packages provide all dependencies: coreutils 9.12, kmod 34.2, mkinitcpio 42.2,
config-m4rch 1.0.0, grub-m4rch 2.16, e2fsprogs 1.47.4, gptfdisk 1.0.10,
util-linux 2.42.4, gzip 1.15, libarchive 3.8.9 and Python 3.14.7. Exact installed
versions and package dependency metadata are saved in `dependencies-audit.json`.

Do not reuse the generic Gravity/GPU-contract package installer for this trial.
Adding a file under `usr/lib/initcpio/*` makes pacman's mkinitcpio helper set
`package=1` and rebuild every preset with `-P`. The same transaction triggers
`99-m4rch-boot-update`, which overwrites normal Image/initramfs/EFI/GRUB from
installed templates. The current template is stale (two 7.1.3 entries/default 0),
so that path also loses the reviewed trial menu. The direct additive path invokes
neither pacman hooks, m4rch-boot-update, grub-mkconfig nor grub-mkstandalone.

## Reviewed installation sequence

Pre-install audit-only command, which makes no writes or mount probes:

```sh
python out/gfx-reset-install/install-additive.py \
  --receipt-sha256 7a906c7dceb97972c1e7316c1736e2a9e2aa5444c960923026ceef36c4c38178
```

Root verifies the native already-mounted root/ESP identities and writable vfat
state before executing. Any separately necessary temporary mode change must
restore the native prior mode. The actual root-owned run required no remount
and left the already-writable native ESP unchanged. The reviewed command is:

```sh
sudo -n python out/gfx-reset-install/install-additive.py --execute \
  --receipt-sha256 7a906c7dceb97972c1e7316c1736e2a9e2aa5444c960923026ceef36c4c38178
```

The installer takes the normal updater's lock, checks root/ESP UUIDs and
PARTUUIDs, verifies writable vfat and sufficient space, and refuses existing
final or partial destinations. It stages and verifies the new module tree and
all boot payloads against fixed reviewed byte counts and SHA256 records. Receipt
JSON is decoded from the same byte blob used for the external digest; menu bytes
are likewise checked against fixed records. The module source tree is about
42.32 MiB and isolated boot payloads about 41.08 MiB.

New modules and boot files publish before the menu. Immediately before atomic
menu replacement, old GRUB and all protected host files must still match review;
new boot payloads are rechecked. After publication the script verifies the new
module/boot trees and preserved host files. The installation receipt binds the
reviewed baseline/current GRUB, new Image/initramfs/module manifest, unchanged
default and absence of reboot/GPU/module operations. Errors record partial new
paths without deleting any previous installation.

Root must inspect `install-result.json` and preserve the native boot mount's
prior mode before arranging a later user-requested reboot. The new entry is fifth/index 4;
installation deliberately keeps default 1, so the trial must be selected explicitly
by root/user. Existing entries 0/1/2/3 remain available. A later normal package update
may regenerate the hand-maintained menu; retain the saved original and additive
configs when handling such a separate update.

## Validation and boundary

GRUB syntax, actual initramfs contents, all 192 module copies and unchanged host
inputs passed offline checks. Default installer audit and wrong-digest refusal
passed before installation. After the intentional menu append, repeating the
pre-install audit correctly refuses the changed current GRUB. The reviewed
historical bytes remain reproducible in `grub-before.cfg`; root's separate
installation evidence records the new host state. Actual Python helper checks reproduced/refused a source-changing-after-
review boot-copy gap, refused wrong staged size and changed menu bytes, and
confirmed receipt decoding uses one hash-bound blob. Independent review covers
all boot artifacts, source/destination scope and publication order.

The future resident candidate is bound to build receipt
`a60d3e4d2a0e54ad3f6818480cbe9c021fc7bbffe4eff7c2495c1c34706144ac`
and owner module
`45ec9be8dded694b3f1c3029cee03018af9061e26500143b9b65371008dc1d6f`.
Installation is not kernel boot qualification or a GPU reset trial. Actual new
kernel notes/build identity and existing PD/USB bindings must be checked after a
separate reboot before any resident-owner hardware action. Backing remains
retained; reset coverage, firmware recovery and DMA retirement are unproven.
