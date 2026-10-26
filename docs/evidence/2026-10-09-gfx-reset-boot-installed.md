# Checked reset kernel installed additively, not yet booted

Root installed the independently reviewed `7.1.13-m4rch-gpu-reset` kernel, matching modules and isolated initramfs. The new fifth GRUB entry is `7.1.13-m4rch-gpu-reset (GFXR001 checked reset trial)`, index4. All five entries remain available. At the user's subsequent request, the default is now4 because they have no GRUB input. The next normal boot selects the new reset kernel automatically. The goal is being paused at the user's request until they report booting it.

The running boot remains `278a044e-6204-4893-83dd-0ef198566470`, kernel `7.1.13-m4rch-gpu-contract`. The old graph owner is still pinned with refcount1, sealed diagnostic only, with all174 DMA pages retained. Root performed no GPU operation, new module load, reset pulse or reboot during this installation. The checked APIs are not available on this old live kernel.

The installer published only `/usr/lib/modules/7.1.13-m4rch-gpu-reset`, `/boot/GFXR001` and an appended GRUB menu. Its exact frozen artifact receipt is `7a906c7dceb97972c1e7316c1736e2a9e2aa5444c960923026ceef36c4c38178`; installer SHA256 is `e9fcd5778c4787553fc1d7b8da818a5c2e8acb30f925c52aa65c0dcb91aa2641`. Root saved a byte-exact source template under `experiments/t6040-gpu/gfx-reset-boot/`.

| Installed artifact | SHA256 |
| --- | --- |
| `/boot/GFXR001/vmlinuz` | `39f25240a6d4ccfdea340c1c8a88915c22e6997b30d1146e3bbba88868a7cbba` |
| `/boot/GFXR001/initramfs.img` | `21343273658f7bef4d0e1e335408ac73f6c5eea5e3c34f183874617bcd8dbdda` |
| `/boot/grub/grub.cfg` after the requested default change | `5cc925334d3b9d783251dc6ae4c6950597e9415cef46d5102fbc0940bedce07a` |
| Original menu saved as `/boot/GFXR001/grub-before.cfg` | `8dd83fc81618e15e09f73ecd4c4c4d550492981c37cfef638e78368a1a777976` |

All208 new module-tree files,192 modules, new boot payloads and16 protected host inputs were checked during staging/publication. The initial menu append preserved its original1398-byte prefix. The later user-requested default change modifies only `set default=1` to `set default=4`; the prior menu is saved as `/boot/GFXR001/grub-default1.cfg`. `out/gfx-reset-install/default-selection.json` records that separate action. Existing kernel/initramfs/EFI/overlay/config files are unchanged. The initramfs preserves the early `dwc3_apple` preload and exact root geometry. No generic package/initramfs/boot-update hooks were invoked. Final installed Image/initramfs/menu hashes were independently read by root after success.

An initial root wrapper refused before any writes because it expected a read-only native boot mount from the restricted tool view. Native sudo actually saw the already-writable vfat `/dev/nvme0n1p3`; the restricted view had added read-only/nosuid/nodev. The corrected wrapper preserved the native mount state and performed no mount/remount operation. `root-mount-policy.json` records identical native before/after options. This partition is separate from the APFS retrieval source `/dev/nvme0n1p5`, which remains unmounted and was accessed only through the previously verified read-only mount.

The successful installer receipt is `out/gfx-reset-install/install-result.json`, SHA256 `44e98bb80c026aceeaea3ced22e4d943455c2ce17365f3a2b5e73e1d3c700c4e`; mount policy SHA256 is `e986ac52439a46d5fb2a263ec33cabc3687310da2053f6ff9a2b1aacf459539f`. No failed hardware wake was repeated. Installation does not qualify a boot, reset coverage, recovery, fresh firmware/DATA, GPU execution or backing retirement.

After selecting the new kernel, revalidate release/notes/new boot ID and PD/USB bindings before the single no-work reset experiment documented in `2026-10-09-gfx-reset-scope-candidate.md`. All memory remains retained after refusal, error or success. Do not append old warm START/INIT sequences or free/unload the joined owner.
