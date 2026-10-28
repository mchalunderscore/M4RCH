#!/bin/bash
# Run in a disposable Debian 13 amd64 VM with Mesa's Debian build dependencies,
# LLVM/Clang 19, gcc-multilib, and the corresponding i386 development libraries.
# Produces a multiarch runtime tree for build-fex-rootfs.sh.
set -euo pipefail
work=${1:-/work}
source=$work/mesa-f2c9dc3fb59c81fdaf51f19884175c856e3d1889
runtime=$work/mesa-runtime
# Apply the same transport changes as native Mesa to both x86 architectures.
patch_file=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../mesa-m4rch" && pwd)/virtio-params.patch
if patch --dry-run --silent -d "$source" -p1 < "$patch_file"; then
    patch -d "$source" -p1 < "$patch_file"
elif ! patch --dry-run --silent --reverse -d "$source" -p1 < "$patch_file"; then
    echo 'Mesa source does not match the virtio parameter patch.' >&2
    exit 1
fi
export LLVM_CONFIG=/usr/bin/llvm-config-19
common=(--prefix=/usr --buildtype=release -Dgallium-drivers=asahi,zink
        -Dvulkan-drivers=asahi -Dvulkan-layers=device-select -Dplatforms=x11,wayland -Dglx=dri
        -Dglvnd=enabled -Degl=enabled -Dgbm=enabled -Dvideo-codecs=[]
        -Dgallium-va=disabled -Dfreedreno-kmds=[] -Dtools=[])
meson setup --reconfigure "$work/mesa64" "$source" "${common[@]}" \
    --libdir=lib/x86_64-linux-gnu -Dllvm=enabled -Dshared-llvm=enabled \
    -Dinstall-mesa-clc=true -Dinstall-precomp-compiler=true
ninja -C "$work/mesa64" -j6
# Use native shader-generation tools when cross compiling the 32-bit driver.
mkdir -p "$work/mesa-tools"
find "$work/mesa64" -type f \( -name mesa_clc -o -name vtn_bindgen2 -o -name asahi_clc \) \
    -exec cp '{}' "$work/mesa-tools/" \;
export PATH="$work/mesa-tools:$PATH"
cat >"$work/i386.ini" <<'EOF'
[binaries]
c = ['gcc', '-m32']
cpp = ['g++', '-m32']
ar = 'gcc-ar'
strip = 'strip'
pkg-config = 'pkg-config'
[properties]
pkg_config_libdir = ['/usr/lib/i386-linux-gnu/pkgconfig', '/usr/share/pkgconfig']
needs_exe_wrapper = true
[host_machine]
system = 'linux'
cpu_family = 'x86'
cpu = 'i686'
endian = 'little'
EOF
meson setup --reconfigure "$work/mesa32" "$source" "${common[@]}" \
    --cross-file="$work/i386.ini" --libdir=lib/i386-linux-gnu \
    -Dllvm=disabled -Dmesa-clc=system -Dprecomp-compiler=system
ninja -C "$work/mesa32" -j6
mkdir -p "$runtime"
DESTDIR="$runtime" ninja -C "$work/mesa64" install
DESTDIR="$runtime" ninja -C "$work/mesa32" install
# Native build tools do not belong in a runtime rootfs.
rm -rf "$runtime/usr/bin"
install -Dm644 "$source/docs/license.rst" "$runtime/usr/share/doc/mesa-aurora/license.rst"

printf '%s\n' 'Mesa virtio GET_PARAMS wire version: 3' > "$runtime/usr/share/doc/mesa-aurora/virtio-params.txt"
