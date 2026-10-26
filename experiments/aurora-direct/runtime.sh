#!/bin/sh
set -u
exec > /run/aurora-direct/startup.log 2>&1
echo 'Aurora AURD001: temporary module and Mesa mounts; speakers excluded'
modprobe_test() { /usr/bin/modprobe -C /run/aurora-direct/modprobe.conf "$@"; }
# Use the test configuration for explicit loads; inherited m4rch blacklists
# continue to apply to unrelated automatic module requests.
for module in apple_pmp apple_soc_cpufreq macsmc_power macsmc_hwmon gpio_macsmc \
              apple_rtkit_helper apple_dockchannel dockchannel_hid \
              phy_apple_t6040_usb2 dwc3_apple sn201202x hci_bcm4377 brcmfmac; do
    modprobe_test "$module" || echo "Module did not load: $module"
done
for module in rtc_macsmc macsmc_reboot pwm_apple leds_pwm aop aop_als aop_las \
              snd_soc_aop snd_soc_cs42l84 snd_soc_apple_mca snd_soc_macaudio apple_isp; do
    modprobe_test "$module" || echo "Optional driver did not load: $module"
done
# /proc/device-tree is a symlink: plain find never descended into it.
# Load the driver explicitly; the admitted DT status controls hardware probe.
case " $(cat /proc/cmdline) " in
    *' m4rch.aurora_gpu=off '*) echo 'GPU explicitly disabled' ;;
    *) modprobe_test asahi || echo 'GPU probe failed; retain framebuffer desktop' ;;
esac
echo 'CPU online/present/possible:'
cat /sys/devices/system/cpu/online /sys/devices/system/cpu/present /sys/devices/system/cpu/possible
ls -l /dev/dri/ 2>/dev/null || true
if [ ! -c /dev/dri/renderD128 ]; then
    echo 'No GPU render node registered; inspect Asahi probe messages in dmesg.'
fi
echo 'Use /run/aurora-direct/with-mesa COMMAND for the separate graphics runtime.'
