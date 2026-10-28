#!/bin/bash
set -euo pipefail
root="$HOME/.local/share/Steam"
support="$root/arm64-support"
if [[ ! -x "$root/steamrtarm64/steam" ]]; then echo 'ARM64 Steam is not installed; run steam-x86 to use the previous client.' >&2; exit 1; fi
mkdir -p "$HOME/.steam"
ln -sfn "$root/steamrtarm64" "$HOME/.steam/bin64"
ln -sfn "$root/steamrtarm64" "$HOME/.steam/binarm64"
ln -sfn "$root/linuxarm64" "$HOME/.steam/sdkarm64"
ln -sfn steamrtarm64 "$root/steamrtarm32"
export PATH="$support/usr/bin:$root/steamapps/common/SteamLinuxRuntime_4-arm64/pressure-vessel/bin:$PATH"
export LD_LIBRARY_PATH="$root/steamrtarm64:$support/usr/lib/aarch64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
cd "$root"
while :; do
  if "$root/steamrtarm64/steam" -noverifyfiles "$@"; then exit 0; else status=$?; fi
  if (( status != 42 )); then exit "$status"; fi
done
