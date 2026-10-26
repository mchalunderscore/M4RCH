#!/bin/sh
set -u
exec > /run/aurora-test/startup.log 2>&1
echo 'Aurora AURT002: temporary module and Mesa mounts; speakers excluded'
modprobe_test() { /usr/bin/modprobe -C /run/aurora-test/modprobe.conf "$@"; }
# Use the test configuration for explicit loads; inherited m4rch blacklists
# continue to apply to unrelated automatic module requests.
for module in apple_pmp apple_soc_cpufreq macsmc_power macsmc_hwmon gpio_macsmc \
              apple_rtkit_helper apple_dockchannel dockchannel_hid \
              phy_apple_t6040_usb2 dwc3_apple sn201202x hci_bcm4377 brcmfmac; do
    modprobe_test "$module" || echo "Module did not load: $module"
done
if find /proc/device-tree -name compatible -exec grep -alq 'apple,agx-t6040' {} \; -print | grep -q .; then
    case " $(cat /proc/cmdline) " in
        *' m4rch.aurora_gpu=off '*) echo 'GPU explicitly disabled' ;;
        *) modprobe_test asahi || echo 'GPU probe failed; retain framebuffer desktop' ;;
    esac
fi
ls -l /dev/dri/ 2>/dev/null || true
echo 'Use /run/aurora-test/with-mesa COMMAND for the separate graphics runtime.'
