#!/bin/sh
# Late, independent controller trials after the SD root and ordinary userspace.
# Keep the alias blocklist: nothing here belongs in the initramfs.
set -eu
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH

group=${1:-}
case $group in platform|usb|nvme) ;; *)
    printf 'Usage: m4rch-enable-peripherals platform|usb|nvme\n' >&2
    exit 2 ;;
esac

compatible=/sys/firmware/devicetree/base/compatible
chosen=/sys/firmware/devicetree/base/chosen
[ -r "$compatible" ] || exit 0
tr '\000' '\n' < "$compatible" | grep -qx 'apple,j614s' || exit 0
[ "$(id -u)" = 0 ] || { printf 'Run with sudo.\n' >&2; exit 1; }
for option in $(cat /proc/cmdline); do
    case $option in
        arch_m4.peripherals=off|arch_m4."$group"=off)
            printf 'm4rch: %s disabled by the boot command line.\n' "$group"
            exit 0 ;;
    esac
done

load()
{
    printf 'm4rch: %s: loading %s\n' "$group" "$1"
    modprobe "$1"
}

case $group in
    platform)
        load spmi-apple-controller
        load apple_nvmem_spmi
        load rtc-macsmc
        load macsmc-reboot
        ;;
    usb)
        # Register the PHY and DWC3 role switch before the PD driver looks
        # them up. DWC3 waits for its cable event before initializing USB2.
        # Left ports stay disabled.
        load phy-apple-t6040-usb2
        load dwc3-apple
        load spmi-apple-controller
        load tps6598x
        ;;
    nvme)
        # An older, still enrolled SD loader does not quiesce ANS. A kernel
        # update alone must never start NVMe against iBoot's live firmware.
        marker=$chosen/arch-m4,ans-handoff
        if [ ! -r "$marker" ] || [ "$(od -An -tx1 "$marker" | tr -d ' \n')" != 763200 ]; then
            printf 'm4rch: NVMe skipped: this loader has no v2 ANS handoff.\n'
            exit 0
        fi
        load apple-sart
        load nvme-apple
        ;;
esac
printf 'm4rch: %s: module requests completed; check driver binding and device I/O.\n' "$group"
