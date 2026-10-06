#!/bin/sh
set -eu
PATH=/usr/bin:/bin:/usr/sbin:/sbin
export PATH
[ "$(id -u)" = 0 ] || { echo 'Run with sudo.' >&2; exit 1; }
[ "$#" = 1 ] || [ "$#" = 2 ] || { echo 'Usage: run.sh NEW_CAPTURE_DIRECTORY [--probe-on-boost]' >&2; exit 1; }
if [ "$#" = 2 ]; then
    [ "$2" = --probe-on-boost ] || exit 1
fi
[ ! -e "$1" ] || { echo 'Use a new capture directory.' >&2; exit 1; }
mountpoint -q /sys/kernel/debug || { echo 'Mount ordinary debugfs first.' >&2; exit 1; }
kit=$(CDPATH= cd -P "$(dirname "$0")" && pwd)
exec python3 -u "$kit/collect.py" --output "$1" ${2+"$2"}
