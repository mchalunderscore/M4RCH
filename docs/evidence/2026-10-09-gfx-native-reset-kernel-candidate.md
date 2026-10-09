# Native-command reset kernel and boot artifact qualification

The separate `7.1.13-m4rch-gpu-native-reset` kernel, all 192 modules and a matching initramfs are built and qualified offline. The modified PMGR object passed a separate `W=1` compilation, followed by the full `Image`, `vmlinux` and module build with `LLVM=1 W=1`. The full build returned zero after approximately 509 seconds. It emitted 692 warnings in unchanged sources, with no diagnostic in the modified PMGR or corrected DWC3 source.

The tree is an isolated copy of the qualified v1 kernel. Source/config/artifact fingerprints of the original maintained tree, v1 tree, existing candidate and installed files remain unchanged. Comparing all 94,004 maintained source entries found only two changed sources: the legacy PMGR observation API plus the additive native-command API, and the previously promoted fixed-host USB role-provider correction. The API header is added relative to the original maintained baseline. Configuration differs only in the requested local version suffix.

The USB correction is integrated into the full new source, SHA-256 `7ca78866b27aa670134ded04820c26b7cabfb17640c410ee5cf3b307e0aa5b0c`. This closes the source/package gap that caused missing role providers in the first v1 boot. The additive API patch is `5df46ea05dbf84d0245a6a74b97f309ca07c1b1d54d3848497ee7cf430bd5264`, final PMGR source `04910407755d029a2acd131f873359bd14983ace946a469725612883835abb61`, and public header `4fbdca1e18ed9c3ee030bad9a94f35c2f70b213d038dfb0555350f35809df9a0`. The new `apple_pmgr_t6040_gfx_native_probe` and both legacy APIs are linked and GPL-exported; no automatic caller is introduced.

## Frozen kernel identity

| Artifact | Identity |
| --- | --- |
| Qualification | `133370f18dc105e7fe310c4945073ad49b64b480e4ca828ced63289a7e34e0d2` |
| Build ID | `16d77884e7ddc1bad8a7e6588fab2009e8c85e1e` |
| Raw kernel notes | `85c56f7a3d7409747dd67fe1dcbf8839562aafab16a9124f9304689a14de437d` |
| Image | `b6831d75dfa0c84c1fb2ecb120027d6202ce7347b860466a68d4eb58c54f1093` |
| vmlinux | `a6d5e33f6f32a5ea9bab7f6284dbae3f4deec5d69fc762b63f0fde2a1c1bc754` |
| Configuration | `68d7b15ac25e1b8bd0230e92b94c29efdcba5421fd95848beee93c031f99641f` |
| Module.symvers | `f6590f8f76c5fa0c48694e479024f0dc3a55c6b2eca1ae5239af8e67768f8fef` |
| Initramfs | `b0831ca98d38f6419fa1bcfa22248d514c34af5cd9646d92c43753b33e2919a5` |

The qualification manifest is `out/gfx-native-reset-kernel/kernel-qualification.json`, with schema `m4rch.gfx-native-reset-kernel-qualification.v1` and `api_profile = native-command-v1`. It separately binds the legacy checked API patch, additive native API patch and known USB correction, with explicit maintained-source exceptions. All 192 built and staged modules use the new release vermagic.

## Boot inputs

`out/gfx-native-reset-install/module-root` contains 208 regular files, the new Image and pkgbase `linux-m4rch-gpu-native-reset`, with no symlinks. `mkinitcpio --nopost` succeeded without sudo or package hooks. Extraction executed no init code. All five embedded early modules match qualified staging. The corrected v1 archive and new archive have identical early members and main member names after release normalization; non-module body changes are limited to release, pkgbase and hook name. Root geometry checks and the early DWC3 preload are preserved.

The initramfs and kernel/module manifests are frozen. Root separately owns the retained GPU owner build, GRUB entry, final combined installer receipt and any later installation. At this build handoff, the installer receipt explicitly awaits those additions and must not be used for installation. This agent performed no installation, mount change, driver load/unload, hardware operation, default selection or reboot.

Compilation and archive qualification do not establish hardware reset coverage, GPU recovery, safe DMA retirement, execution or a successful boot. Those remain native trial questions; all existing resident backing remains under root's separate ownership. The JSON companion binds build, preservation, module and archive evidence without changing historical v1 receipts.
