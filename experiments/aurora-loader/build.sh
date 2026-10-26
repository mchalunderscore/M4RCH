#!/bin/sh
# Run inside the existing ARM Linux build VM, after prepare.py.
set -eu
work=${1:-/work/aurora-native-loader}
output=/project/out/aurora-loader
export SOURCE_DATE_EPOCH=1792800000
export CARGO_HOME=/work/direct-cargo
export PATH=/work/direct-build-bin:$PATH
cd "$work/m1n1"
make -j8 BUILDSTD=1 RELEASE=1 M1N1_VERSION_TAG=AURL001-9f7cdfbd \
    CARGO_FLAGS='-Z build-std=alloc,core --locked' > "$output/m1n1-build.log" 2>&1
cd "$work/uboot"
make apple_sdboot_defconfig > "$output/uboot-build.log" 2>&1
make -j8 UBOOTRELEASE=2026.07-AURL001 LOCALVERSION= >> "$output/uboot-build.log" 2>&1
python3 /project/experiments/aurora-loader/package.py "$work" "$output"
