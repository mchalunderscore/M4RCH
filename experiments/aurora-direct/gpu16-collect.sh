#!/bin/sh
set -eu
[ -f /run/aurora-direct/gpu16-candidate.json ] || { echo 'Boot the AURG016 candidate first'; exit 1; }
recorded=$(cat /run/aurora-direct/return-path 2>/dev/null || true)
destination=${1:-${recorded:-/boot/AURG016/return-$(date -u +%Y%m%dT%H%M%SZ)}}
if [ "$(findmnt -n -o UUID --target /boot)" != 33CE-1F10 ]; then
    echo 'Mount the Arch ESP at /boot before collecting'; exit 1
fi
mkdir -p "$destination"
# The early recorder already owns the return directory. Keep each full
# snapshot separate; the base collector deliberately requires a new directory.
destination=$destination/full-$(date -u +%Y%m%dT%H%M%SZ)-$$
sh /run/aurora-direct/collect-base.sh "$destination"
cp /run/aurora-direct/gpu16-candidate.json "$destination/candidate.json"
{
    modinfo asahi
    cat /run/aurora-direct/modprobe.conf
    if [ -r /sys/module/asahi/notes/.note.gnu.build-id ]; then
        sha256sum /sys/module/asahi/notes/.note.gnu.build-id
    fi
    printf '\nGPU module parameters:\n'
    for p in /sys/module/asahi/parameters/*; do
        [ ! -r "$p" ] || { printf '%s: ' "$p"; cat "$p"; }
    done
} >"$destination/gpu-module.txt" 2>&1 || true
prefix=/opt/m4rch-aurora-direct1
timeout -k 5 30 /run/aurora-direct/with-mesa "$prefix/bin/vulkaninfo" --summary >"$destination/vulkaninfo.txt" 2>&1 || true
timeout -k 5 30 /run/aurora-direct/with-mesa "$prefix/bin/eglinfo" -B -p surfaceless >"$destination/eglinfo.txt" 2>&1 || true
{
    for executable in kwin_wayland plasmashell Xorg sddm; do
        pgrep -a "$executable" || true
    done
    systemctl status display-manager.service --no-pager || true
} >"$destination/desktop.txt" 2>&1
if id alice >/dev/null 2>&1; then
    uid=$(id -u alice)
    for qdbus in /usr/bin/qdbus6 /usr/lib/qt6/bin/qdbus; do
        [ -x "$qdbus" ] || continue
        timeout -k 5 10 runuser -u alice -- env "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$uid/bus" "$qdbus" org.kde.KWin /KWin supportInformation >"$destination/kwin-support.txt" 2>&1 || true
        break
    done
fi
dmesg >"$destination/dmesg-after-graphics.txt"
echo "GPU16 return bundle: $destination"
