#!/bin/sh
set -eu
PATH=/usr/bin:/bin:/usr/sbin:/sbin
export PATH
[ "$(id -u)" = 0 ] || { echo 'Run with sudo.' >&2; exit 1; }
[ "$#" = 2 ] || { echo 'Usage: run.sh CPU NEW_CAPTURE_DIRECTORY' >&2; exit 1; }
case "$1" in 0|1|8) ;; *) echo 'CPU must be 0, 1 or 8 for this guarded trial.' >&2; exit 1 ;; esac
[ ! -e "$2" ] || { echo 'Capture directory already exists.' >&2; exit 1; }
kit=$(CDPATH= cd -P "$(dirname "$0")" && pwd)
python3 "$kit/verify.py"
mountpoint -q /sys/kernel/debug || { echo 'Mount ordinary debugfs first.' >&2; exit 1; }
[ ! -d /sys/module/m4rch_pmu_fixed ] || { echo 'Trial already loaded; investigate first.' >&2; exit 1; }
for source in /sys/bus/event_source/devices/*; do
    case "${source##*/}" in software|breakpoint|tracepoint|kprobe|uprobe) ;;
    *) echo "Unexpected event source $source; review ownership first." >&2; exit 1 ;; esac
done
insmod "$kit/m4rch_pmu_fixed.ko" cpu="$1"
trap 'rmmod m4rch_pmu_fixed' 0
trap 'exit 1' HUP INT TERM
python3 "$kit/collect.py" --cpu "$1" --output "$2"
