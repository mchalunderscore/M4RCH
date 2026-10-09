# Separate Gravity kernel candidate with the reviewed GFX reset API

The separate candidate at `out/gfx-reset-kernel/linux` builds successfully as
`7.1.13-m4rch-gpu-reset`. It contains the reviewed driver-owned GFX snapshot and
checked pulse API. No reset API is called automatically. This work prepared a
kernel and matching modules; it did not install them, edit boot files, reboot,
load a module or touch GPU hardware.

The stable future-module input is
`out/gfx-reset-kernel/kernel-qualification.json`, SHA256
`47e6e5c9027da74d3b98b4877415f24cd393baf2858c9567d73da2f31e0ec95b`. It records exact release, configuration,
Image, vmlinux, raw ELF notes and Module.symvers paths and hashes. The resident
owner must be rebuilt against this candidate and qualify the actual future boot
before using either API.

## Source and configuration preservation

The starting tree is the existing maintained/guarded Gravity contract kernel,
`out/gpu-gravity-contract/linux`, revision
`3b85d81f656af14d0fc4bea3eef87fe040c424f9`. It was copied with `cp -a --reflink=auto`,
never linked to the original. All 94,004 baseline source entries were inventoried;
94,003 remain identical in the candidate. The only existing source edit is
`drivers/pmdomain/apple/pmgr-pwrstate.c`; the only added source is
`include/linux/soc/apple/pmgr-gfx-reset.h`. Their hashes match the reviewed patch
and the independently replayed 98-case actual C fault model.

Reviewed patch SHA256:
`b08f6785ce938b20fcd1d1ededd49ffca04242263ac0e7a0bc7f6f6f3678821c`.

The candidate retains all existing CPU/PD/USB/T6040 changes and guarded GPU
identification behavior. All 39 baseline maintained fingerprints match the saved
contract receipt; 38 remain identical in the candidate, with the PMGR driver as
the deliberately changed exception. The guarded GPU entry and G16 profile are
unchanged, including the existing block on normal T6040 GPU startup.

The configuration differs by exactly one line:

```diff
-CONFIG_LOCALVERSION=""
+CONFIG_LOCALVERSION="-m4rch-gpu-reset"
```

`CONFIG_LOCALVERSION_AUTO` remains disabled. `LOCALVERSION=` is passed explicitly
to make to suppress the extra `+` used for an untagged/dirty tree. The first
release query saw copied stale `include/config/auto.conf` and returned `7.1.13`;
this diagnostic is retained. `make syncconfig` refreshed generated configuration,
and the natural release then matched `7.1.13-m4rch-gpu-reset`. No forced
`KERNELRELEASE` override was used.

Full per-file hashes, both local diffs against the pinned Git revision, the one
untracked baseline G16 profile copy, copy/inode checks, symlink audit, toolchain
versions and configuration diff are saved under `out/gfx-reset-kernel/`.
Independent review also recomputed all 94,004 source hashes in both trees and
found no original-tree changes or shared source inodes.

## Build and identity

The candidate reused copied baseline build outputs and completed an incremental
rebuild with four jobs, bounded against roughly 10 GiB of available RAM:

```sh
make -C out/gfx-reset-kernel/linux ARCH=arm64 LLVM=1 LOCALVERSION= -j4 Image vmlinux modules
```

Build exit status was zero. Existing Rust RTKit/Asahi code emitted nonfatal
unused/deprecated/dead-code warnings, saved with source context in
`build-warnings.txt`; the PMGR C change produced no diagnostic. Compiler versions
are Clang/LLD 23.1.1 and Rust 1.99.0, matching the baseline configuration. Exact
commands, output and hashes are in `build-receipt.json` and `build.log`.

| Artifact | SHA256 |
| --- | --- |
| `.config` | `4fd12970263896c67682fe6c118d47670d974ac8b5124bbfb50d9357c699d982` |
| `arch/arm64/boot/Image` | `39f25240a6d4ccfdea340c1c8a88915c22e6997b30d1146e3bbba88868a7cbba` |
| `vmlinux` | `aae5efbe4f76bcbe7fe944dd5c381197f870cb8cf1e247c5d7d2d716eec1f579` |
| `Module.symvers` | `7eed25823375827049e5e9f8672394aa2a93a4d7850670d496bb246068445b99` |
| Raw `.notes` (`kernel.notes.bin`) | `73827a9260e9c49f49036380e62c14d8f2a535edabb808914af7ecbcec05f013` |

GNU kernel build ID: `56bf77789b445b0e35cda49f621ff79122eb8d77`. The raw notes were extracted from
ELF section bytes without modifying vmlinux; `llvm-readelf --notes` independently
reports the same build ID. Generated `kernel.release` and `UTS_RELEASE` both
match the candidate release.

Both functions are linked into vmlinux and recorded as `EXPORT_SYMBOL_GPL` in
Module.symvers:

- `apple_pmgr_t6040_gfx_snapshot`
- `apple_pmgr_t6040_gfx_checked_pulse`

All 192 built modules have vermagic beginning with the candidate release,
including guarded Asahi and both USB controller/Type-C modules. Modules were
stripped and staged only under
`out/gfx-reset-kernel/staging/lib/modules/7.1.13-m4rch-gpu-reset` using
`INSTALL_MOD_PATH`; no host module directory was changed. No package or
initramfs has been generated. The future installer must retain the existing
NVMe initramfs/boot procedure and a working fallback.

Original matching-tree `.config`, Module.symvers, vmlinux, Image, generated
identity/config headers and Git HEAD/index hashes remain equal to their saved
pre-copy values. Baseline source and prior receipts were left unchanged.

## Qualification boundary

The API implementation and error cleanup were already independently reviewed and
validated by 98 actual C fault cases, including committed write errors and
uncertain auto-policy cleanup. This build qualifies integration and future
module compilation. It does not qualify a new boot, the real kernel device/lock
wrapper, physical reset coverage, ASC/GPU restart or DMA retirement.

Any future pulse remains one deliberately selected idle/no-work experiment,
with publication stopped and all GPU/DMA backing retained. A successful command
readback cannot authorize backing release. Native RTBuddy/ASC power/reset
analysis may still refine the experiment before it runs.
