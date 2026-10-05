#!/bin/sh
# Read existing kernel state. Never load modules, mount filesystems, or open disks.
PATH=/usr/sbin:/usr/bin:/sbin:/bin
LC_ALL=C
export PATH LC_ALL
umask 077

output=
if [ "$#" -eq 2 ] && [ "$1" = --output ] && [ -n "$2" ]; then
    output=$2
elif [ "$#" -ne 0 ]; then
    printf 'Usage: sudo m4rch-driver-diagnostics [--output FILE]\n' >&2
    exit 2
fi
if [ "$(id -u)" != 0 ]; then
    printf 'Run this collector with sudo so it can read the current boot logs.\n' >&2
    exit 1
fi

if [ -n "$output" ]; then
    case $output in /*) ;; *) output=./$output ;; esac
    if [ -d "$output" ]; then
        printf 'The output path is a directory: %s\n' "$output" >&2
        exit 1
    fi
    directory=${output%/*}
    temporary=$(mktemp "$directory/.m4rch-driver-diagnostics.XXXXXX") || exit 1
    trap '[ -z "$temporary" ] || rm -f "$temporary"' 0
    trap 'exit 1' HUP INT TERM
    if ! sh "$0" >"$temporary" 2>&1; then
        printf 'Collection failed; the previous report was preserved.\n' >&2
        cat "$temporary" >&2
        exit 1
    fi
    if [ ! -s "$temporary" ] ||
        [ "$(tail -n 1 "$temporary")" != 'End of driver diagnostics.' ]; then
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

run()
{
    printf '\n--'
    printf ' %s' "$@"
    printf ' --\n'
    if ! command -v "$1" >/dev/null 2>&1; then
        printf 'Command unavailable.\n'
    elif command -v timeout >/dev/null 2>&1; then
        timeout -k 2s 15s "$@" 2>&1
        result=$?
        [ "$result" -eq 0 ] || printf 'Command exit status: %s\n' "$result"
    else
        "$@" 2>&1
        result=$?
        [ "$result" -eq 0 ] || printf 'Command exit status: %s\n' "$result"
    fi
}

show_file()
{
    if [ -r "$1" ]; then
        run cat "$1"
    fi
}

filesystem_state()
{
    section 'Mount namespaces and ext4 error state'
    # ext4 can report rw while refusing writes with emergency_ro. Preserve
    # both per-mount flags and filesystem error records before another boot.
    # Limit proc output; sysfs error attributes are individual scalar values.
    if [ -r "$1/self/mountinfo" ]; then
        run head -c 1048576 "$1/self/mountinfo"
    fi
    for filesystem in "$2"/*; do
        [ -d "$filesystem" ] && [ -r "$filesystem/errors_count" ] || continue
        printf '\n%s\n' "$filesystem"
        for attribute in errors_count warning_count msg_count \
            first_error_time first_error_errcode first_error_func first_error_line \
            first_error_ino first_error_block last_error_time last_error_errcode \
            last_error_func last_error_line last_error_ino last_error_block; do
            if [ -r "$filesystem/$attribute" ]; then
                run head -c 4096 "$filesystem/$attribute"
            fi
        done
    done
}

usb_connection_state()
{
    section 'USB-C connection and role state (read-only)'
    for class in typec usb_role; do
        printf '\n-- %s class --\n' "$class"
        found=0
        for device in "$1/class/$class/"*; do
            [ -d "$device" ] || continue
            found=1
            printf '\n%s\n' "$device"
            for attribute in uevent data_role power_role port_type preferred_role \
                orientation power_operation_mode vconn_source usb_power_delivery_revision \
                usb_typec_revision supports_usb_power_delivery role; do
                show_file "$device/$attribute"
            done
        done
        [ "$found" = 1 ] || printf 'No registered devices in this class.\n'
    done
    printf '\n-- USB device attachment --\n'
    for device in "$1/bus/usb/devices/"*; do
        [ -d "$device" ] || continue
        printf '\n%s\n' "$device"
        for attribute in busnum devnum devpath idVendor idProduct product \
            speed version authorized bDeviceClass bInterfaceClass power/runtime_status; do
            show_file "$device/$attribute"
        done
    done
}

usb_host_port_state()
{
    section 'xHCI host port status (read-only)'
    found=0
    # Read only PORTSC snapshots. Other xHCI debugfs files include controls
    # and bandwidth reports with different access requirements.
    for portsc in "$1"/usb/xhci/*/ports/port*/portsc; do
        [ -r "$portsc" ] || continue
        found=1
        show_file "$portsc"
    done
    [ "$found" = 1 ] || printf 'No readable xHCI port status files; debugfs may be unavailable or unmounted.\n'
}

usb_role_graph()
{
    section 'Live right-port USB role graph (device-tree bytes, read-only)'
    # Restrict reads to the reviewed properties; empty boolean files still
    # establish presence. Hex bytes preserve big-endian phandles exactly.
    for node in soc/usb@392280000 \
        soc/usb@392280000/port/endpoint \
        soc/spmi@509198000/usb-pd@c/connector \
        soc/spmi@509198000/usb-pd@c/connector/port/endpoint; do
        printf '\n%s\n' "$1/$node"
        if [ ! -d "$1/$node" ]; then
            printf 'Node absent.\n'
            continue
        fi
        for property in status dr_mode maximum-speed usb-role-switch \
            arch-m4,usb-wait-for-cable apple,force-host-mode data-role power-role \
            phandle remote-endpoint; do
            if [ -r "$1/$node/$property" ]; then
                printf '%s: present\n' "$property"
                run od -An -tx1 -N 256 "$1/$node/$property"
            fi
        done
    done
}

section 'Kernel, boot and module identity'
run uname -a
run pacman -Q linux-m4rch config-m4rch
run date -u
show_file /proc/cmdline
show_file /proc/uptime
show_file /proc/sys/kernel/tainted
show_file /proc/modules
show_file /etc/modprobe.d/m4rch-drivers.conf
if [ -r /sys/firmware/devicetree/base/chosen/arch-m4,ans-handoff ]; then
    printf '\nANS handoff marker: '
    tr '\000' '\n' < /sys/firmware/devicetree/base/chosen/arch-m4,ans-handoff
fi
run ls -ld /usr/lib/modules/*
if [ -r /proc/config.gz ]; then
    run gzip -dc /proc/config.gz
fi

section 'Kernel log before device inspection'
run dmesg

section 'CPU, memory, interrupts and current mounts'
show_file /proc/cpuinfo
show_file /proc/meminfo
show_file /proc/interrupts
show_file /proc/mounts
show_file /proc/swaps
filesystem_state /proc /sys/fs/ext4

section 'Bound and unbound device inventory'
for bus in platform pci usb spmi i2c spi hid; do
    [ -d "/sys/bus/$bus/devices" ] || continue
    printf '\n-- %s bus --\n' "$bus"
    for device in "/sys/bus/$bus/devices/"*; do
        [ -d "$device" ] || continue
        printf '\n%s\n' "$device"
        if [ -L "$device/driver" ]; then
            printf 'driver: '
            readlink "$device/driver"
        else
            printf 'driver: unbound\n'
        fi
        for attribute in modalias uevent power/runtime_status; do
            show_file "$device/$attribute"
        done
        if [ -r "$device/of_node/compatible" ]; then
            printf 'compatible: '
            tr '\000' '\n' < "$device/of_node/compatible"
        fi
    done
done
show_file /sys/kernel/debug/devices_deferred

section 'Block device metadata (no device files are opened)'
for device in /sys/class/block/*; do
    [ -d "$device" ] || continue
    printf '\n%s\n' "$device"
    for attribute in dev size ro uevent device/model device/state; do
        show_file "$device/$attribute"
    done
done

section 'USB, Type-C and available device nodes'
run lsusb
run lsusb -t
run ls -l /sys/class/typec
usb_connection_state /sys
usb_host_port_state /sys/kernel/debug
usb_role_graph /sys/firmware/devicetree/base
run ls -l /dev/dri /dev/snd /dev/video* /dev/rtc* /dev/kvm

section 'Power, clocks, thermal and hardware sensors'
run m4rch-power-report --runtime
for directory in /sys/class/power_supply/* /sys/class/thermal/thermal_zone* \
    /sys/class/thermal/cooling_device* /sys/class/hwmon/* /sys/devices/system/cpu/cpufreq/policy*; do
    [ -d "$directory" ] || continue
    printf '\n%s\n' "$directory"
    for attribute in name type status online present capacity voltage_now current_now power_now \
        charge_now charge_full energy_now energy_full temp trip_point_0_temp \
        cur_state max_state scaling_driver scaling_governor scaling_cur_freq \
        scaling_min_freq scaling_max_freq cpuinfo_cur_freq; do
        show_file "$directory/$attribute"
    done
    for attribute in "$directory"/temp*_input "$directory"/temp*_label \
        "$directory"/fan*_input "$directory"/fan*_label "$directory"/power*_input \
        "$directory"/in*_input "$directory"/curr*_input; do
        show_file "$attribute"
    done
done
show_file /sys/power/state
show_file /sys/power/mem_sleep
show_file /sys/kernel/debug/pm_genpd/pm_genpd_summary
show_file /sys/kernel/debug/clk/clk_summary

section 'Failed services and current boot kernel journal'
run systemctl --no-pager --failed
run systemctl --no-pager status m4rch-platform.service m4rch-usb.service m4rch-nvme.service
run journalctl --no-pager -b -u m4rch-usb.service
run journalctl --no-pager -b -k
section 'Kernel log after device inspection'
run dmesg
printf '\nEnd of driver diagnostics.\n'
