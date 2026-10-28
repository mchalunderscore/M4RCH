#!/bin/bash
set -euo pipefail
printf 'Kernel: '; uname -r
printf '\nPlasma output:\n'
kscreen-doctor -o
printf '\nPanel backlight:\n'
for f in brightness max_brightness actual_brightness; do printf '%s=' "$f"; cat "/sys/class/backlight/apple-panel-bl/$f"; done
printf '\nDisplay messages since boot:\n'
journalctl -b -k --no-pager | rg -i 'HDR test:|apple-dcp.*(fail|error|timeout|crash|mode_set|set_mode:|brightness)' | tail -80 || true
