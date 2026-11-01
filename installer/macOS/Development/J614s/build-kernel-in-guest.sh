#!/bin/bash
# Run as a non-root user in a disposable aarch64 Linux build environment.
set -euo pipefail

if (( $# != 5 )); then
  printf '%s\n' 'Usage: build-kernel-in-guest.sh SOURCE OUTPUT LLVM DEPS BINDGEN_DIR' >&2
  exit 2
fi
source_dir=$(realpath "$1")
output_dir=$(realpath "$2")
llvm_dir=$(realpath "$3")
deps_dir=$(realpath "$4")
bindgen_dir=$(realpath "$5")
[[ $(uname -s) == Linux && $(uname -m) == aarch64 && $(id -u) != 0 ]] || {
  printf '%s\n' 'Requires a non-root aarch64 Linux builder.' >&2
  exit 1
}
grep -Eq '^CapEff:[[:space:]]+0+$' /proc/self/status || {
  printf '%s\n' 'The build process must have no effective Linux capabilities.' >&2
  exit 1
}
[[ $source_dir != "$output_dir" && -f $source_dir/Makefile && -f $output_dir/.config ]] || exit 1
grep -qx 'CONFIG_SND_SEQUENCER=m' "$output_dir/.config"
grep -qx 'CONFIG_DM_INTEGRITY=m' "$output_dir/.config"
grep -qx 'CONFIG_LOCALVERSION="-m4rch-aurora1"' "$output_dir/.config"
export PATH="$bindgen_dir/bin:$llvm_dir/bin:$deps_dir/usr/bin:$PATH"
export LD_LIBRARY_PATH="$llvm_dir/lib:$deps_dir/usr/lib/aarch64-linux-gnu"
export LIBCLANG_PATH="$llvm_dir/lib"
export BISON_PKGDATADIR="$deps_dir/usr/share/bison"
export HOSTCFLAGS="-I$deps_dir/usr/include"
export HOSTLDFLAGS="-L$deps_dir/usr/lib/aarch64-linux-gnu"
export KBUILD_BUILD_USER=m4rch KBUILD_BUILD_HOST=aurora-builder
export KBUILD_BUILD_TIMESTAMP='2026-10-31 00:00:00 UTC'
jobs=${AURORA_BUILD_JOBS:-10}
[[ $jobs =~ ^[1-9][0-9]*$ ]] || { printf '%s\n' 'Invalid build worker count.' >&2; exit 1; }
make -C "$source_dir" O="$output_dir" ARCH=arm64 LLVM=1 rustavailable
make -C "$source_dir" O="$output_dir" ARCH=arm64 LLVM=1 -j"$jobs" Image modules dtbs
