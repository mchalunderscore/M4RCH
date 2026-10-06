#!/bin/sh
set -eu
PATH=/usr/bin:/bin:/usr/sbin:/sbin
export PATH
[ "$(id -u)" = 0 ] || { echo 'Run with sudo.' >&2; exit 1; }
[ "$#" = 1 ] || [ "$#" = 3 ] || { echo 'Usage: run.sh NEW_CAPTURE_DIRECTORY [--samples 30|720]' >&2; exit 1; }
kit=$(CDPATH= cd -P "$(dirname "$0")" && pwd)
# Validate optional sampling arguments before loading the module.
if [ "$#" = 3 ]; then
    [ "$2" = --samples ] || { echo 'Expected --samples.' >&2; exit 1; }
    case "$3" in 30|720) ;; *) echo 'Samples must be 30 or 720.' >&2; exit 1 ;; esac
fi
python3 "$kit/verify.py"
mountpoint -q /sys/kernel/debug || { echo 'Mount debugfs at /sys/kernel/debug first.' >&2; exit 1; }
[ ! -d /sys/module/m4rch_smc_readonly ] || { echo 'Diagnostic is already loaded; investigate first.' >&2; exit 1; }
insmod "$kit/m4rch_smc_readonly.ko"
trap 'rmmod m4rch_smc_readonly' 0
trap 'exit 1' HUP INT TERM
python3 "$kit/capture.py" "$@"
