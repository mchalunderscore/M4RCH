#!/bin/sh
set -eu
root=${1:?native root mount required}
runtime=/run/aurora-userspace
prefix=$runtime/opt/m4rch-aurora-direct1
mkdir -p "$runtime/vulkan-icds" "$runtime/egl-vendors"
cp "$prefix/share/vulkan/icd.d/asahi_icd.aarch64.json" "$runtime/vulkan-icds/"
cp "$prefix/share/glvnd/egl_vendor.d/50_mesa.json" "$runtime/egl-vendors/"
# KWin carries CAP_SYS_NICE. Secure loaders ignore environment overrides, so
# expose the candidate through their trusted discovery paths for this boot.
for target in /usr/share/vulkan/icd.d /etc/vulkan/icd.d /usr/local/share/vulkan/icd.d /etc/xdg/vulkan/icd.d; do
    if [ "$target" != /usr/share/vulkan/icd.d ] && [ ! -d "$root$target" ]; then continue; fi
    mkdir -p "$root$target"
    mount --bind "$runtime/vulkan-icds" "$root$target"
done
for target in /usr/share/glvnd/egl_vendor.d /etc/glvnd/egl_vendor.d; do
    if [ "$target" != /usr/share/glvnd/egl_vendor.d ] && [ ! -d "$root$target" ]; then continue; fi
    mkdir -p "$root$target"
    mount --bind "$runtime/egl-vendors" "$root$target"
done
