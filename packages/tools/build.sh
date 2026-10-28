#!/bin/bash
set -euo pipefail
mkdir -p /work/packages-new
for name in linux-m4rch m1n1-m4rch u-boot-m4rch linux-firmware-vendor-m4rch alsa-ucm-conf-m4rch asahi-scripts-m4rch mesa-m4rch virglrenderer-m4rch mesa-flatpak-m4rch muvm-m4rch fex-emu-m4rch avd-fw-m4rch fex-rootfs-debian-m4rch steam-m4rch mbpfan-m4rch vesktop-m4rch; do
    build=/work/packages-new/$name
    if [[ $name == mesa-m4rch && -d /work/mesa-next/src ]]; then
        build=/work/mesa-next
    fi
    mkdir -p "$build"
    cp -a /project/out/packages/recipes/"$name"/. "$build/"
    chown -R builder:builder "$build"
    (cd "$build"; runuser -u builder -- makepkg --config /work/makepkg.conf --cleanbuild --nodeps --noconfirm --force)
    # Copy the version just built, rather than every archived version.
    rm -f /project/out/packages/"$name"-*.pkg.tar.zst
    (cd "$build"; runuser -u builder -- makepkg --config /work/makepkg.conf --packagelist) |
        while IFS= read -r archive; do cp "$archive" /project/out/packages/; done
done
