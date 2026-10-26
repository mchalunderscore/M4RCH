#!/bin/sh
set -u
destination=$1
mkdir -p "$destination"
dmesg >"$destination/dmesg.txt"
cp /sys/firmware/fdt "$destination/live.dtb" 2>/dev/null || true
cp /run/aurora-direct/startup.log "$destination/startup.log" 2>/dev/null || true
{
    uname -a
    cat /proc/cmdline
    ls -l /dev/dri /sys/class/drm
    for node in /sys/class/drm/card*-*; do
        [ -d "$node" ] || continue
        echo "$node"
        for attribute in status enabled modes; do
            [ ! -r "$node/$attribute" ] || { echo "$attribute"; cat "$node/$attribute"; }
        done
    done
    echo 'DCP004 loader and bridge evidence:'
    for property in m4rch,dcp-summary m4rch,dcp-identity m4rch,dcp-observed-uuid m4rch,dcp-dart-0 m4rch,dcp-dart-1 m4rch,dcp-dart-2 m4rch,dcp-bridge-summary; do
        path=/sys/firmware/devicetree/base/chosen/$property
        [ ! -r "$path" ] || { printf '%s: ' "$property"; tr -d '\000' <"$path"; printf '\n'; }
    done
    echo 'Kernel backlight interfaces and display options:'
    for path in /sys/module/appledrm/parameters/j614s_modeset /sys/module/appledrm/parameters/show_notch /sys/module/appledrm/parameters/t6041_dcpext /sys/class/backlight/*/brightness /sys/class/backlight/*/max_brightness /sys/class/backlight/*/actual_brightness; do
        [ ! -r "$path" ] || { echo "$path"; cat "$path"; }
    done
    for path in /sys/kernel/debug/dri/*/state /sys/kernel/debug/dri/*/name /sys/kernel/debug/devices_deferred; do
        [ ! -r "$path" ] || { echo "$path"; timeout -k 1 2 cat "$path"; }
    done
} >"$destination/display-state.txt" 2>&1
systemctl status aurora-direct.service display-manager.service --no-pager >"$destination/services.txt" 2>&1 || true
sync -f "$destination"
