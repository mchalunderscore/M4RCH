#!/bin/sh
set -eu
for attempt in 1 2 3 4 5; do
    [ ! -s /run/aurora-direct/return-path ] || break
    sleep 1
done
destination=$(cat /run/aurora-direct/return-path)
# Exercise standard ICD discovery, including for KWin's secure execution mode.
# This runs alongside desktop startup and never gates it.
timeout -k 2 25 env -u VK_DRIVER_FILES -u VK_ICD_FILENAMES -u LD_LIBRARY_PATH \
    VK_LOADER_DEBUG=error,warn,driver \
    /opt/m4rch-aurora-direct1/bin/vulkaninfo --summary >"$destination/vulkan-startup.txt" 2>&1 || true
sync -f "$destination"
