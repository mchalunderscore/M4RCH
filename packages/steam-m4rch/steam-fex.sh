#!/bin/bash
# Keep FEX's path socket visible when pressure-vessel creates a private /run.
# Abstract sockets alone do not survive a child's new network namespace.
set -euo pipefail
runtime=${XDG_RUNTIME_DIR:-/run/user/$UID}
socket=${FEX_SERVERSOCKETPATH:-$UID.FEXServer.Socket}
if [[ $socket != /* ]]; then
    socket="$runtime/$socket"
fi
if [[ -S $socket ]]; then
    case ":${PRESSURE_VESSEL_FILESYSTEMS_RW:-}:" in
        *":$socket:"*) ;;
        *) export PRESSURE_VESSEL_FILESYSTEMS_RW="${PRESSURE_VESSEL_FILESYSTEMS_RW:+$PRESSURE_VESSEL_FILESYSTEMS_RW:}$socket" ;;
    esac
fi
exec /bin/bash /usr/lib/steam/bin_steam.sh "$@"
