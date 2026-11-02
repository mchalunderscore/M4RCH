#!/bin/sh
# Build against the system Wayland protocol and run against the selected Mesa.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
work=$(mktemp -d "${TMPDIR:-/tmp}/mesa-zink-surface.XXXXXXXX")
trap 'rm -rf "$work"' EXIT HUP INT TERM
protocol=$(pkg-config --variable=pkgdatadir wayland-protocols)/stable/xdg-shell/xdg-shell.xml
wayland-scanner client-header "$protocol" "$work/xdg-shell-client-protocol.h"
wayland-scanner private-code "$protocol" "$work/xdg-shell-protocol.c"
${CC:-gcc} -O2 -Wall -Wextra -Werror -I "$work" "$here/repro.c" \
  "$work/xdg-shell-protocol.c" -o "$work/repro" \
  $(pkg-config --cflags --libs wayland-client wayland-egl egl glesv2)
MESA_LOADER_DRIVER_OVERRIDE=zink GALLIUM_DRIVER=zink "$work/repro" "$@"
