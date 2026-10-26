#!/bin/sh
set -eu
output=/project/out/aurora-bootstrap
work=/work/aurora-native-loader
export SOURCE_DATE_EPOCH=1792800000
export CARGO_HOME=/work/direct-cargo
export PATH=/work/direct-build-bin:$PATH
cd "$work/stage1"
git submodule update --init --depth=1 > "$output/stage1-artwork.log" 2>&1
make -j8 BUILDSTD=1 RELEASE=1 CHAINLOADING=1 M1N1_VERSION_TAG=AUBS001-stage1 \
    CARGO_FLAGS='-Z build-std=alloc,core --locked --features chainload' > "$output/stage1-build.log" 2>&1
python3 tools/fill_stage1_config.py --input build/m1n1.bin --output "$output/stage1.bin" \
    --esp-partuuid 5fdb35c6-3a66-416d-8358-6555fd99fcc5 --stage2-path boot.bin --window-ms 0
cd "$work/uboot"
make -j8 UBOOTRELEASE=2026.07-AUBS001 LOCALVERSION= > "$output/uboot-build.log" 2>&1
python3 /project/experiments/aurora-bootstrap/package.py
