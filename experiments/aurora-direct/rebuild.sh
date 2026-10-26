#!/bin/sh
# Native ARM64 Linux rebuild, with /project bind mounted and sources in /work.
# Source integration and package prerequisites are described in README.md.
set -eu
kit=/project/experiments/aurora-direct
out=/project/out/aurora-direct
cd /work/linux
test "$(git rev-parse HEAD^{tree})" = d6b171e95516b1683968d220800acee244c01869
cp "$out/previous.config" .config
scripts/kconfig/merge_config.sh -m .config arch/arm64/configs/asahi.config
scripts/config --set-str LOCALVERSION '-m4rch-aurora-direct1' --disable LOCALVERSION_AUTO \
    --enable EFI_STUB --enable IKCONFIG --enable IKCONFIG_PROC --disable DRM_APPLE \
    --disable SND_SOC_TAS2764 --disable SND_SOC_TAS2770 --module SND_SOC_APPLE_MACAUDIO --module SND_SOC_APPLE_AOP_AUDIO --module APPLE_AOP --module SND_SOC_CS42L84 --module IIO_AOP_ALS --module IIO_AOP_LAS --module VIDEO_APPLE_ISP \
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
cp arch/arm64/boot/dts/apple/t6040-j614s-aurora-direct.dtb "$out/template.dtb"
release=$(cat "$out/kernel.release")
mkdir -p "/work/direct-modules/lib/modules/$release"
rsync -a --exclude=snd-soc-tas2764.ko --exclude=snd-soc-tas2770.ko --exclude=build --exclude=source \
    "/work/kernel-install/lib/modules/$release/" "/work/direct-modules/lib/modules/$release/"
depmod -b /work/direct-modules "$release"
tar -C /work/direct-modules -czf "$out/modules.tar.gz" "lib/modules/$release"
echo 'Kernel artifacts ready; build the loader and Mesa using their pinned recipes.'
