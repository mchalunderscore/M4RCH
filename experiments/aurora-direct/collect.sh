#!/bin/sh
set -eu
[ "$(id -u)" = 0 ] || { echo 'Run with sudo'; exit 1; }
destination=${1:-/boot/AURD001/return-$(date -u +%Y%m%dT%H%M%SZ)}
if [ "$#" = 0 ] && [ "$(findmnt -n -o UUID --target /boot)" != 33CE-1F10 ]; then
    echo 'Mount the Arch ESP at /boot before collecting logs'; exit 1
fi
mkdir "$destination"
uname -a >"$destination/uname.txt"
cat /proc/cmdline >"$destination/cmdline.txt"
dmesg >"$destination/dmesg.txt"
journalctl -b --no-pager >"$destination/journal.txt"
cp /sys/firmware/fdt "$destination/live.dtb"
[ ! -f /run/aurora-direct/startup.log ] || cp /run/aurora-direct/startup.log "$destination/startup.log"
lsmod >"$destination/lsmod.txt"
lsblk -o NAME,TYPE,SIZE,FSTYPE,UUID,PARTUUID,MOUNTPOINTS >"$destination/storage.txt"
lsusb -t >"$destination/usb.txt" 2>&1 || true
find /sys/class/drm -maxdepth 2 -type l -print >"$destination/drm.txt"
cat /sys/devices/system/cpu/online >"$destination/cpus.txt"
cat /sys/devices/system/cpu/present /sys/devices/system/cpu/possible >"$destination/cpu-masks.txt"
cat /proc/cpuinfo >"$destination/cpuinfo.txt"
lscpu -e >"$destination/cpu-topology.txt" 2>&1 || true
cat /proc/bus/input/devices >"$destination/input-devices.txt"
journalctl -b -u display-manager --no-pager >"$destination/display-manager.txt" 2>&1 || true
ls -l /dev/dri /sys/class/drm >"$destination/dri.txt" 2>&1 || true
for path in /sys/devices/system/cpu/cpufreq/policy*/scaling_cur_freq \
            /sys/class/hwmon/hwmon*/name /sys/class/hwmon/hwmon*/temp*_input; do
    [ -f "$path" ] || continue
    printf '%s: ' "$path" >>"$destination/sensors.txt"
    cat "$path" >>"$destination/sensors.txt"
done
cat /proc/asound/cards >"$destination/audio-cards.txt" 2>&1 || true
# Class entries are symlinks; find without -L does not reach their attributes.
{
    for path in /sys/class/video4linux/*/name /sys/bus/iio/devices/*/name; do
        [ -f "$path" ] || continue
        printf '%s: ' "$path"
        cat "$path"
    done
} >"$destination/camera-iio.txt" 2>&1
{
    for path in /sys/bus/usb/devices/*; do
        [ -d "$path" ] || continue
        printf '%s\n' "$path"
        for attribute in manufacturer product speed; do
            [ ! -f "$path/$attribute" ] || {
                printf '  %s: ' "$attribute"
                cat "$path/$attribute"
            }
        done
    done
} >"$destination/usb-sysfs.txt" 2>&1
{
    for path in /sys/bus/platform/devices/*.gpu /sys/bus/platform/devices/*.isp \
                /sys/bus/platform/devices/*.aop /sys/bus/platform/devices/*.mca \
                /sys/bus/platform/devices/*.usb; do
        [ -d "$path" ] || continue
        printf '%s: ' "$path"
        if [ -L "$path/driver" ]; then readlink "$path/driver"; else echo unbound; fi
    done
} >"$destination/driver-bindings.txt" 2>&1
if [ -r /sys/kernel/debug/devices_deferred ]; then
    cat /sys/kernel/debug/devices_deferred >"$destination/devices-deferred.txt"
else
    echo 'devices_deferred unavailable; debugfs may not be mounted' >"$destination/devices-deferred.txt"
fi
systemctl status aurora-direct.service --no-pager >"$destination/runtime-service.txt" 2>&1 || true
echo "Saved $destination"
