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
