# Reproduce the offline builds

These commands belong in an ext4 Linux working directory, using the exact
revisions in sources.json. They do not create a maintained-kernel boot trial.
The checked-in config is the successful Gravity 7.1.13+ offline build, not the
working 7.1.3-m4rch config. It must not replace the maintained profile.

Required tools: Clang/LLVM, Rust with matching rust-src, bindgen, make, bc,
flex/bison, Meson/Ninja, Python Mako/YAML/packaging, libdrm, libclc and the LLVM
SPIR-V translator. The evidence receipt records the versions used.

After checking out Gravity Linux 3b85d81f656af14d0fc4bea3eef87fe040c424f9:

```sh
# GPU_REPO is the m4rch checkout; run these commands inside the Gravity tree.
git apply "$GPU_REPO/patches/gravity-linux-t6040-metadata.patch"
mkdir ../gpu-kernel-build
cp "$GPU_REPO/experiments/t6040-gpu/configs/gravity-offline.config" ../gpu-kernel-build/.config
make O=../gpu-kernel-build LLVM=1 rustavailable
make O=../gpu-kernel-build LLVM=1 olddefconfig
make O=../gpu-kernel-build LLVM=1 -j4 vmlinux
make O=../gpu-kernel-build LLVM=1 -j4 drivers/gpu/drm/asahi/asahi_m4.ko
```

Building vmlinux supplies matching exported Rust/kernel symbols for modpost.
Do not suppress undefined symbols to manufacture a module. The result is for
that offline kernel; do not insmod it into the maintained boot.

In Gravity bootloader 950e6b7f268e71cf77889f27a760782bf898b651:

```sh
git apply "$GPU_REPO/patches/gravity-bootloader-t6040-metadata.patch"
make build/kboot_gpu.o
```

This verifies the actual C translation unit, not a linked/installed loader.

In Gravity Mesa 87ac51d411f0e58a9433567ec2666f457be89e1d:

```sh
git apply "$GPU_REPO/patches/gravity-mesa-t6040-metadata.patch"
meson setup ../gpu-mesa-build --prefix="$GPU_REPO/out/gpu-mesa-prefix" \
  -Dgallium-drivers=asahi -Dvulkan-drivers= -Dplatforms= -Dllvm=enabled \
  -Dglx=disabled -Degl=enabled -Dgbm=enabled
ninja -C ../gpu-mesa-build -j4
meson install -C ../gpu-mesa-build --no-rebuild
```

Installation stays in the ignored workspace prefix. G16S discovery explicitly
returns an unqualified-layout failure; this build does not prove rendering.
`make check` in m4rch compiles/runs the metadata fixtures and parser regressions.

## Maintained-kernel resource preflight

`build-identify.py` accepts a maintained 7.1.3 source tree after the Wallace,
SMP, trackpad and experimental-hardware patch stack has been reconstructed.
It checks the final protected driver hashes before adding the leaf Rust module.
Seed it with the running maintained config, not the Gravity offline config:

```sh
python3 experiments/t6040-gpu/build-identify.py out/gpu-maintained/linux-build \
  --config out/gpu-maintained/maintained-running.config \
  --receipt out/gpu-maintained/identify-build-inputs-final.json --jobs 4
```

The isolated release is 7.1.3-m4rch-gpu-id. This builds Image and matching
modules; it does not install them, create an initramfs, edit GRUB or change DT.
The script can safely repeat its Kconfig/Makefile additions. The leaf module
matches only `m4rch,t6040-gpu-identify`, validates the exact named SGX resource,
and returns before mapping when its default `read_ids=0` remains in force.
`identify-preflight.dtsi` is a disabled candidate resource node without a power
binding or the access-review acknowledgement. It must be compiled with the
maintained board DT and explicitly reviewed before an isolated boot trial.

The current Linux genpd report shows `gfx off-0`, with AFR/GPX on. Live boot ADT
names gate 400 GFX-SGX and 402 GFX-BUSY; both have the no_ps flag. GFX-SGX's parent
is GFX (386), whose group/offset matches existing ps_gfx. This is evidence for
reviewing the parent path, not permission to access an unpowered SGX window.
The first trial can validate the Rust-enabled kernel and resource-only probe
without any GPU reads. Power/reset/clock qualification precedes ID reads, which
also require both read_ids=1 and m4rch,id-access-reviewed=1. No firmware
startup, MCC writes, rendering or display replacement is implemented.

For a fresh native reconstruction, create disposable `linux` and `wallace`
checkouts in a new workspace at the revisions in sources.lock.json, then run
`python3 experiments/t6040-gpu/prepare-maintained.py WORKSPACE`. This copies
Wallace's DT/patch inputs and applies the verified maintained driver stack; it
refuses an existing linux-build. It does not rebuild or install the loader.

On this Linux installation, `package-identify.py WORKSPACE` creates a separate
linux-m4rch-gpu-id package from the built artifacts and installed maintained
initramfs inputs. It requires `identify-build-inputs-final.json` and checks its
source/config digests. The package has its own module tree, kernel file,
initramfs hook, config and preset. It does not replace linux-m4rch. Packaging
requires an ordinary user's native makepkg/fakeroot environment; the script
does not install the package. Native installation also triggers the project's
normal boot-update hook, so preserve normal boot backups and generate the trial
initramfs explicitly with `mkinitcpio -p linux-m4rch-gpu-id`.

## Temporary native resource and parent-power tests

Both helpers build separately against the successfully booted trial kernel:

```sh
python3 experiments/t6040-gpu/build-helper.py out/gpu-maintained resource-overlay
python3 experiments/t6040-gpu/build-helper.py out/gpu-maintained gfx-power-test
```

Neither command loads a module. Native tests used exact running/build GNU build-ID
agreement, temporary loads and unconditional cleanup. Raw logs remain in ignored
out/gpu-maintained. Never load these into a different kernel just because the
release string looks similar.

resource-overlay adds a new simple-bus subtree with only the bounded named SGX
resource. It explicitly populates only that subtree. Embedded FDT must be eight-
byte aligned; the initial unaligned trial was rejected before adding nodes.
Load the Rust driver explicitly with read_ids0 before the overlay, then unload
the Rust driver before removing the overlay. There is no power/clock/reset
binding and no access-review flag. Native driver binding, off GFX state, and
complete node/module removal were verified. No GPU mapping or reads occurred.

The gfx-power-test helper looks up the existing registered GFX provider by its
reviewed DT path, checks the offset/size/label/cell-count, and uses
of_genpd_add_device plus normal runtime-PM APIs. It invents no phandle and calls
no SGX/reset/clock/firmware APIs. Native genpd states were off0 -> on -> off0;
runtime suspend returned0 and the consumer was removed. This exercises PMGR
writes through the existing driver, not direct GPU MMIO. It does not establish
GPU reset/clock/ID access semantics or firmware readiness. The external helper
sets the expected out-of-tree kernel taint; that persists after unloading.

See docs/evidence/2026-10-06-gpu-resource-bind.json and
2026-10-06-gfx-genpd-trial.json for native receipts. Subsequent ID reads still
need review; do not add the access acknowledgement merely because a parent
domain can turn on.
