#!/bin/sh
# Native ARM64 Linux rebuild, with /project bind mounted and sources in /work.
# Source integration and package prerequisites are described in README.md.
set -eu
kit=/project/experiments/aurora-test
out=/project/out/aurora-test
cd /work/linux
test "$(git rev-parse HEAD^{tree})" = d570356031a315f307bdddb034e7f307dd6d2972
cp "$out/previous.config" .config
scripts/kconfig/merge_config.sh -m .config arch/arm64/configs/asahi.config
scripts/config --set-str LOCALVERSION '-m4rch-aurora-test2' --disable LOCALVERSION_AUTO \
    --enable EFI_STUB --enable IKCONFIG --enable IKCONFIG_PROC --disable DRM_APPLE \
    --disable SND_SOC_TAS2764 --disable SND_SOC_TAS2770 --disable SND_SOC_APPLE_MACAUDIO \
    --disable INFINIBAND --disable INFINIBAND_USER_ACCESS --disable INFINIBAND_USER_MAD \
    --disable RDMA_RXE --disable RDMA_SIW --enable ARM64_SME --enable TMPFS \
    --enable DEVTMPFS --enable BLK_DEV_INITRD --enable RD_GZIP --enable RD_ZSTD \
    --enable EXT4_FS --enable FAT_FS --enable VFAT_FS --enable EFI_PARTITION
make LLVM=1 olddefconfig
python3 "$kit/prepare_board.py" /work/linux
git diff --exit-code -- drivers/firmware/efi/libstub/fdt.c
make LLVM=1 -j8 Image modules
make LLVM=1 INSTALL_MOD_PATH=/work/kernel-install modules_install
cp arch/arm64/boot/Image "$out/Image"
cp .config "$out/kernel.config"
cp System.map "$out/System.map"
make -s LLVM=1 kernelrelease > "$out/kernel.release"
cp arch/arm64/boot/dts/apple/t6040-j614s-aurora-test.dtb "$out/template.dtb"
tar --exclude=build --exclude=source -C /work/kernel-install -czf "$out/modules.tar.gz" lib/modules
cd /work/aurora-uboot
python3 "$kit/prepare_loader.py" /work/aurora-uboot --template "$out/template.dtb"
make apple_sdboot_defconfig
make UBOOTRELEASE=2026.07 LOCALVERSION= -j8
python3 "$kit/prepare_loader.py" /work/aurora-uboot --template "$out/template.dtb" --pack "$out/boot.bin"
cd /work/mesa
meson setup build --prefix=/opt/m4rch-aurora-test2 -Dbuildtype=release \
    -Dgallium-drivers=asahi -Dvulkan-drivers=asahi -Dplatforms=x11,wayland \
    -Dglx=dri -Degl=enabled -Dgbm=enabled -Dllvm=enabled -Dvideo-codecs=[] \
    -Dgallium-va=disabled -Dtools=[] -Dbuild-tests=true
ninja -C build -j4
DESTDIR=/work/mesa-install ninja -C build install
tar -C /work/mesa-install -czf "$out/mesa.tar.gz" .
cc -g -O1 -fsanitize=address,undefined -Wall -Wextra -Werror -Wno-sign-compare \
    "$kit/test_handoff.c" -lfdt -o /work/test-handoff
echo 'Run test-handoff against the recorded ADT fixtures and meson test --suite asahi.'
echo 'On macOS: package.py --base-initramfs /Volumes/M4RCHESP/AURA001/initramfs.img, then stage.py.'
