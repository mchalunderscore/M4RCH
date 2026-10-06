#!/bin/sh
set -eu
PATH=/usr/bin:/bin:/usr/sbin:/sbin
export PATH
[ "$(id -u)" = 0 ] || { echo 'Run with sudo.' >&2; exit 1; }
kit=$(CDPATH= cd -P "$(dirname "$0")" && pwd)
case $(uname -s) in
    Linux)
        sh "$kit/rollback-update/install.sh"
        python3 "$kit/restore-boot.py"
        echo 'Accepted packages and boot files restored; reboot normally.'
        ;;
    Darwin) python3 "$kit/restore-boot.py" ;;
    *) exit 1 ;;
esac
