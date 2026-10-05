#!/bin/sh
# Input/backlight diagnostics; never opens event devices or profiles.
PATH=/usr/sbin:/usr/bin:/sbin:/bin
LC_ALL=C
export PATH LC_ALL

output=
if [ "$#" -eq 2 ] && [ "$1" = --output ] && [ -n "$2" ]; then
    output=$2
elif [ "$#" -ne 0 ]; then
    printf 'Usage: sudo m4rch-input-diagnostics [--output FILE]\n' >&2
    exit 2
fi
if [ "$(id -u)" != 0 ]; then
    printf 'Run this collector with sudo so it can read the current boot logs.\n' >&2
    exit 1
fi

if [ -n "$output" ]; then
    # A failed collector/sudo invocation in a pipe to tee can silently replace
    # a useful report with an empty file. Publish only a completed collection.
    case $output in
        /*) ;;
        *) output=./$output ;;
    esac
    if [ -d "$output" ]; then
        printf 'The output path is a directory: %s\n' "$output" >&2
        exit 1
    fi
    directory=${output%/*}
    temporary=$(mktemp "$directory/.m4rch-input-diagnostics.XXXXXX") || exit 1
    trap '[ -z "$temporary" ] || rm -f "$temporary"' 0
    trap 'exit 1' HUP INT TERM
    if ! sh "$0" >"$temporary" 2>&1; then
        printf 'Collection failed; the previous report was preserved.\n' >&2
        cat "$temporary" >&2
        exit 1
    fi
    if [ ! -s "$temporary" ] ||
        [ "$(tail -n 1 "$temporary")" != 'End of input diagnostics.' ]; then
        printf 'Collection was incomplete; the previous report was preserved.\n' >&2
        cat "$temporary" >&2
        exit 1
    fi
    bytes=$(wc -c <"$temporary") || exit 1
    mv -f "$temporary" "$output" || exit 1
    temporary=
    if ! sync; then
        printf 'Report saved to %s, but flushing it to disk failed.\n' "$output" >&2
        exit 1
    fi
    printf 'Saved %d bytes to %s\n' "$bytes" "$output"
    exit 0
fi

section()
{
    printf '\n== %s ==\n' "$1"
}

show_file()
{
    printf '\n-- %s --\n' "$1"
    if [ -r "$1" ]; then
        cat "$1"
    else
        printf 'Not available.\n'
    fi
}

section 'Kernel and boot arguments'
uname -a
show_file /proc/cmdline

section 'Running kernel input configuration'
if [ -r /proc/config.gz ] && command -v gzip >/dev/null 2>&1; then
    gzip -dc /proc/config.gz | grep -E '^(CONFIG_(UHID|BT_HIDP|HID_GENERIC|HID_MAGICMOUSE|APPLE_DOCKCHANNEL_HID|PWM_APPLE|LEDS_PWM)=|# CONFIG_(UHID|BT_HIDP) is not set)'
    if command -v sha256sum >/dev/null 2>&1; then
        printf 'SHA-256 of the running kernel configuration: '
        gzip -dc /proc/config.gz | sha256sum
    fi
else
    printf '/proc/config.gz is unavailable; uname alone cannot distinguish our rebuilt kernels.\n'
fi

section 'Registered input devices'
show_file /proc/bus/input/devices
printf '\nDevice node metadata (no events are read):\n'
ls -ld /dev/input /dev/input/event* /dev/uhid 2>&1

section 'Input event sysfs metadata and udev properties'
for event in /sys/class/input/event*; do
    [ -d "$event" ] || continue
    printf '\n-- %s --\n' "$event"
    for attribute in name phys uniq modalias; do
        if [ -r "$event/device/$attribute" ]; then
            printf '%s: ' "$attribute"
            cat "$event/device/$attribute"
        fi
    done
    if command -v udevadm >/dev/null 2>&1; then
        udevadm info --query=property --path="$event" 2>&1
    fi
done

section 'LED brightness'
for led in /sys/class/leds/*; do
    [ -d "$led" ] || continue
    printf '\n-- %s --\n' "$led"
    for attribute in brightness max_brightness; do
        if [ -r "$led/$attribute" ]; then
            printf '%s: ' "$attribute"
            cat "$led/$attribute"
        fi
    done
done

if command -v journalctl >/dev/null 2>&1; then
    section 'Current boot kernel journal'
    journalctl --no-pager -b -k 2>&1
    section 'Current boot Bluetooth service journal'
    journalctl --no-pager -b -u bluetooth.service 2>&1
    section 'Current boot logind journal'
    journalctl --no-pager -b -u systemd-logind.service 2>&1
else
    section 'Kernel log (journalctl unavailable)'
    dmesg 2>&1
fi

section 'Xorg logs'
found=no
for log in /home/alarm/.local/share/xorg/Xorg.*.log /var/log/Xorg.*.log; do
    [ -f "$log" ] || continue
    found=yes
    show_file "$log"
done
[ "$found" = yes ] || printf 'No Xorg log files found at the standard alarm/system paths.\n'
printf '\nEnd of input diagnostics.\n'
