#!/bin/sh
set -eu
# Apple's Linux build VM has no Landlock; keep repository signature checks.
grep -q '^DisableSandbox$' /etc/pacman.conf || sed -i '/^\[options\]$/a DisableSandbox' /etc/pacman.conf
mkdir -p /work
pacman-key --init
pacman-key --populate archlinuxarm
pacman -Syu --noconfirm --needed base-devel meson ninja python-mako python-yaml python-packaging python-ply python-jinja libdrm libglvnd wayland wayland-protocols libx11 libxext libxfixes libxshmfence libxxf86vm libxcb libxrandr libxdamage expat zstd zlib libelf llvm clang libclc spirv-tools spirv-llvm-translator vulkan-headers glslang libdisplay-info xcb-util-keysyms rust rust-bindgen mkinitcpio kmod pipewire-audio wireplumber alsa-ucm-conf vulkan-tools mesa-utils
id builder >/dev/null 2>&1 || useradd -m builder
