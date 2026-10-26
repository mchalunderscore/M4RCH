#!/bin/sh
set -eu
[ "$(findmnt -n -o UUID --target /boot)" = 33CE-1F10 ] || exit 1
boot_id=$(cat /proc/sys/kernel/random/boot_id)
destination=/boot/AURG016/return-$(date -u +%Y%m%dT%H%M%SZ)-$boot_id
mkdir -p "$destination"
printf '%s\n' "$destination" >/run/aurora-direct/return-path
cp /run/aurora-direct/gpu16-candidate.json "$destination/candidate.json"
cat /proc/cmdline >"$destination/cmdline.txt"
{
    getcap /usr/bin/kwin_wayland 2>/dev/null || true
    for directory in /usr/share/vulkan/icd.d /etc/vulkan/icd.d /usr/share/glvnd/egl_vendor.d; do
        findmnt --target "$directory" || true
        for manifest in "$directory"/*.json; do
            [ ! -f "$manifest" ] || { echo "$manifest"; cat "$manifest"; }
        done
    done
} >"$destination/driver-discovery.txt" 2>&1
timeout -k 2 90 journalctl -b --follow --lines=all --no-pager -o short-monotonic >"$destination/journal-live.txt" 2>&1 &
journal_pid=$!
timeout -k 2 90 dmesg --follow >"$destination/dmesg-live.txt" 2>&1 &
kernel_pid=$!
trap 'kill "$journal_pid" "$kernel_pid" 2>/dev/null || true; sync -f "$destination"' EXIT
trap 'exit 0' TERM INT
# Bound collection to the startup window and flush it during short attempts.
count=0
while [ "$count" -lt 18 ]; do
    sleep 5
    sync -f "$destination"
    count=$((count + 1))
done
wait "$journal_pid" 2>/dev/null || true
wait "$kernel_pid" 2>/dev/null || true
