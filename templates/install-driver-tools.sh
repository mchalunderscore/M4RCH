#!/bin/sh
# Run in Linux from the copied driver-tools directory. No module is loaded here.
set -eu
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH
umask 022

fail()
{
    printf 'install-driver-tools: %s\n' "$*" >&2
    exit 1
}

[ "$#" -eq 0 ] || fail 'Run this installer without arguments.'
[ "$(uname -s)" = Linux ] || fail 'Run this installer inside the Arch installation.'
[ "$(id -u)" = 0 ] || fail 'Run this installer with sudo.'
command -v python3 >/dev/null 2>&1 || fail 'Install the Arch python package first.'
command -v depmod >/dev/null 2>&1 || fail 'Install the Arch kmod package first.'
source_dir=$(CDPATH= cd -P "$(dirname "$0")" && pwd)
[ -f "$source_dir/install-driver-modules.py" ] &&
    [ ! -L "$source_dir/install-driver-modules.py" ] || fail 'Missing regular module installer.'
exec python3 "$source_dir/install-driver-modules.py" "$source_dir"
