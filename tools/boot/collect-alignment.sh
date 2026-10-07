#!/bin/sh
# Read-only native checks for a stage-2 loader update.
set -eu
umask 077
if [ "$(id -u)" != 0 ]; then
    echo 'Run sudo sh /boot/loader-alignment/collect.sh' >&2
    exit 1
fi
base=${1:-/boot/loader-alignment}
stamp=$(date -u +%Y%m%dT%H%M%SZ)
out=$(mktemp -d "$base/return-$stamp-XXXXXX")
capture() {
    name=$1
    shift
    "$@" > "$out/$name.txt" 2>&1 || printf '\nCommand failed: %s\n' "$*" >> "$out/$name.txt"
}
capture uname uname -a
capture packages pacman -Q linux-m4rch config-m4rch
capture mounts findmnt
capture block-devices lsblk -o NAME,SIZE,FSTYPE,UUID,PARTUUID,MOUNTPOINTS
capture kernel-log journalctl -b -k --no-pager
capture failed-services systemctl --failed --no-pager
capture boot-bundle sha256sum /boot/boot.bin
capture usb lsusb
capture bluetooth bluetoothctl show
if [ -r /sys/firmware/fdt ]; then
    cat /sys/firmware/fdt > "$out/live.dtb"
fi
{
    for file in /sys/firmware/devicetree/base/chosen/*; do
        [ -f "$file" ] || continue
        printf '\n%s\n' "$file"
        od -An -tx1c "$file"
    done
} > "$out/chosen.txt"
{
    for file in /sys/devices/system/cpu/cpu[0-9]*/cpuidle/state*/name \
                /sys/devices/system/cpu/cpu[0-9]*/cpuidle/state*/usage \
                /sys/devices/system/cpu/cpu[0-9]*/cpuidle/state*/time \
                /sys/devices/system/cpu/cpu[0-9]*/cpu_capacity; do
        [ -r "$file" ] || continue
        printf '%s: ' "$file"
        cat "$file"
    done
} > "$out/cpu-idle-capacity.txt"
for file in /boot/loader-alignment/profile.json /boot/loader-alignment/loader-manifest.json; do
    [ ! -f "$file" ] || cp "$file" "$out/"
done
printf '%s\n' 'Add your observations to HANDOVER.md here: desktop/input, USB, Bluetooth, audio, shutdown/reboot, and any regression.' > "$out/HANDOVER.md"
tar -czf "$out.tar.gz" -C "$base" "$(basename "$out")"
echo "Return bundle: $out.tar.gz"
