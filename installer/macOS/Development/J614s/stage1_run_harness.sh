#!/bin/bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  printf '%s\n' "Usage: $0 /path/to/readable-m4rch-stage1.bin" >&2
  exit 2
fi
here=$(cd -- "$(dirname -- "$0")" && pwd -P)
macos_root=$(cd -- "$here/../.." && pwd -P)
scratch=$(mktemp -d "${TMPDIR:-/tmp}/j614s-stage1.XXXXXXXX")
trap 'rm -rf -- "$scratch"' EXIT

swiftc -parse-as-library -module-cache-path "$scratch/cache" -emit-module -emit-object \
  -module-name AuroraFirmware "$here/stage1_firmware_stub.swift" \
  -emit-module-path "$scratch/AuroraFirmware.swiftmodule" -o "$scratch/firmware.o"
swiftc -parse-as-library -module-cache-path "$scratch/cache" -I "$scratch" \
  "$macos_root/Sources/AuroraAppleInstaller/NativeBootChain.swift" \
  "$here/stage1_harness.swift" "$scratch/firmware.o" -lz -o "$scratch/stage1-harness"
"$scratch/stage1-harness" "$1"
