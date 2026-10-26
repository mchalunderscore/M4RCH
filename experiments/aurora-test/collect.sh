#!/bin/sh
set -eu
[ "$(id -u)" = 0 ] || { echo 'Run with sudo'; exit 1; }
destination=${1:-/boot/AURT002/return-$(date -u +%Y%m%dT%H%M%SZ)}
mkdir "$destination"
uname -a >"$destination/uname.txt"
cat /proc/cmdline >"$destination/cmdline.txt"
dmesg >"$destination/dmesg.txt"
journalctl -b --no-pager >"$destination/journal.txt"
cp /sys/firmware/fdt "$destination/live.dtb"
cp /run/aurora-test/startup.log "$destination/startup.log"
lsmod >"$destination/lsmod.txt"
lsblk -o NAME,TYPE,SIZE,FSTYPE,UUID,PARTUUID,MOUNTPOINTS >"$destination/storage.txt"
lsusb -t >"$destination/usb.txt" 2>&1 || true
find /sys/class/drm -maxdepth 2 -type l -print >"$destination/drm.txt"
cat /sys/devices/system/cpu/online >"$destination/cpus.txt"
for path in /sys/devices/system/cpu/cpufreq/policy*/scaling_cur_freq \
            /sys/class/hwmon/hwmon*/name /sys/class/hwmon/hwmon*/temp*_input; do
    [ -f "$path" ] || continue
    printf '%s: ' "$path" >>"$destination/sensors.txt"
    cat "$path" >>"$destination/sensors.txt"
done
echo "Saved $destination"
