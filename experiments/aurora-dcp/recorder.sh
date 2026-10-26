#!/bin/sh
set -eu
[ "$(findmnt -n -o UUID --target /boot)" = 33CE-1F10 ] || exit 1
boot_id=$(cat /proc/sys/kernel/random/boot_id)
destination=/boot/AUDP001/return-$(date -u +%Y%m%dT%H%M%SZ)-$boot_id
mkdir -p "$destination"
printf '%s\n' "$destination" >/run/aurora-direct/return-path
cp /run/aurora-direct/gpu16-candidate.json "$destination/candidate.json"
cat /proc/cmdline >"$destination/cmdline.txt"
cp /sys/firmware/fdt "$destination/live.dtb" || true
# Bound persistent output even if firmware or userspace emits a log storm.
timeout -k 2 300 journalctl -b --follow --lines=all --no-pager -o short-monotonic | head -c 16777216 >"$destination/journal-live.txt" &
journal_pid=$!
timeout -k 2 300 dmesg --follow | head -c 16777216 >"$destination/dmesg-live.txt" &
kernel_pid=$!
trap 'kill "$journal_pid" "$kernel_pid" 2>/dev/null || true; sync -f "$destination"' EXIT
trap 'exit 0' TERM INT
# Capture before driver startup, during takeover, and after desktop startup.
count=0
while [ "$count" -lt 60 ]; do
    sh /run/aurora-direct/collect-display.sh "$destination/latest" || true
    sleep 5
    count=$((count+1))
done
