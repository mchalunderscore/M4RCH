#!/bin/sh
# Native Linux metadata and logs: no module loads, bus writes or disk contents.
set -eu
PATH=/usr/bin:/bin:/usr/sbin:/sbin
LC_ALL=C
export PATH LC_ALL
umask 077

usage()
{
    cat <<'EOF'
Usage: sudo sh diagnose.sh [--non-interactive] [--output NEW-DIRECTORY] [--user USER]

Run after installing this update and rebooting into the KDE desktop.
The default tests both USB-C plug orientations on the right-hand port.
--non-interactive captures the current state once, without prompts.
--output names a new report directory; its parent must already exist.
Otherwise reports are saved beside this update directory, normally in /boot.
--user chooses the desktop user when not invoked through that user's sudo.

Pair a Bluetooth headset and select its audio profile in KDE before running
if testing audio. The script queries audio state; it does not record sound.
Optional missing commands are recorded in the report. An incomplete run
keeps its captured files. A successful run creates a .tar.gz beside them.
EOF
}

interactive=1
output=
audio_user=${SUDO_USER:-}
while [ "$#" -gt 0 ]; do
    case $1 in
        --non-interactive) interactive=0; shift ;;
        --output|--user)
            [ "$#" -ge 2 ] && [ -n "$2" ] || { usage >&2; exit 2; }
            case $1 in --output) output=$2 ;; --user) audio_user=$2 ;; esac
            shift 2 ;;
        --help|-h) usage; exit 0 ;;
        *) usage >&2; exit 2 ;;
    esac
done
[ "$(uname -s)" = Linux ] || { printf 'Run this in Arch Linux.\n' >&2; exit 1; }
[ "$(id -u)" = 0 ] || { printf 'Run with sudo from your desktop user.\n' >&2; exit 1; }
if [ "$interactive" = 1 ] && [ ! -t 0 ]; then
    printf 'Interactive capture needs a terminal; use --non-interactive for one snapshot.\n' >&2
    exit 1
fi
kit=$(CDPATH= cd -P "$(dirname "$0")" && pwd)
(cd "$kit" && sha256sum -c DIAGNOSTICS-SHA256SUMS) || exit 1

stamp=$(date -u +%Y%m%dT%H%M%SZ)
if [ -n "$output" ]; then
    case $output in /*) ;; *) output=$(pwd)/$output ;; esac
    [ ! -e "$output" ] && [ ! -L "$output" ] || {
        printf 'Output already exists; choose a new directory: %s\n' "$output" >&2
        exit 1
    }
    [ ! -e "$output.tar.gz" ] && [ ! -L "$output.tar.gz" ] || exit 1
    mkdir "$output"
    report=$(CDPATH= cd -P "$output" && pwd)
else
    report=$(mktemp -d "${kit%/*}/diagnostics-$stamp-XXXXXX")
fi
[ ! -e "$report.tar.gz" ] && [ ! -L "$report.tar.gz" ] || {
    printf 'Archive already exists: %s.tar.gz\n' "$report" >&2
    exit 1
}
printf 'Capture has not completed. Keep these files if interrupted.\n' >"$report/INCOMPLETE.txt"
archive_temporary=
cleanup()
{
    result=$?
    [ -z "$archive_temporary" ] || rm -f "$archive_temporary"
    if [ "$result" -ne 0 ]; then
        printf 'Collection or archive finalization did not complete.\n' >"$report/INCOMPLETE.txt" || :
        rm -f "$report/COMPLETE.txt"
        printf 'Capture incomplete; existing evidence is in %s\n' "$report" >&2
    fi
}
trap cleanup 0
trap 'exit 1' HUP INT TERM

run()
{
    printf '\n--'
    printf ' %s' "$@"
    printf ' --\n'
    if ! command -v "$1" >/dev/null 2>&1; then
        printf 'Command unavailable.\n'
    else
        result=0
        timeout -k 2s 15s "$@" 2>&1 || result=$?
        [ "$result" = 0 ] || printf 'Command exit status: %s\n' "$result"
    fi
}

# Do not inherit root's cwd or connection overrides when querying Alice's audio.
audio_uid=
audio_home=
case $audio_user in
    -*|*[!A-Za-z0-9_.-]*) printf 'Invalid desktop username.\n' >&2; exit 2 ;;
esac
if [ -n "$audio_user" ] && [ "$audio_user" != root ]; then
    audio_uid=$(id -u "$audio_user" 2>/dev/null) || audio_uid=
    audio_home=$(getent passwd "$audio_user" | cut -d: -f6) || audio_home=
fi
run_audio()
{
    (cd / && run runuser -u "$audio_user" -- env -i \
        PATH="$PATH" LC_ALL=C HOME="$audio_home" USER="$audio_user" LOGNAME="$audio_user" \
        XDG_RUNTIME_DIR="/run/user/$audio_uid" \
        DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$audio_uid/bus" "$@")
}

{
    printf 'Update directory: %s\nReport directory: %s\n' "$kit" "$report"
    printf 'Desktop user: %s\nUID: %s\nHOME: %s\n' "$audio_user" "$audio_uid" "$audio_home"
    printf 'Interactive USB phases: %s\nUTC: %s\n' "$interactive" "$stamp"
    run uname -a
    run pacman -Q linux-m4rch config-m4rch bluez bluez-utils pipewire pipewire-audio pipewire-pulse wireplumber libfido2
    run findmnt --target "$report"
    printf '\nPackage checksums for this update:\n'
    cat "$kit/SHA256SUMS"
    printf '\nDiagnostic helper checksums:\n'
    cat "$kit/DIAGNOSTICS-SHA256SUMS"
} >"$report/capture-info.txt" 2>&1

prompt()
{
    printf '\n%s\nPress Enter when ready: ' "$1"
    read -r response || { printf '\nInput ended before the next phase.\n' >&2; exit 1; }
}

snapshot()
{
    phase=$1
    printf '\nCollecting %s ...\n' "$phase"
    {
        printf 'Phase: %s\nUTC: ' "$phase"
        date -u +%Y-%m-%dT%H:%M:%SZ
        printf 'Uptime: '
        cat /proc/uptime
    } >"$report/$phase-time.txt"
    timeout -k 5s 180s sh "$kit/m4rch-driver-diagnostics" \
        --output "$report/$phase-drivers.txt"
    {
        run lspci -nnk
        run ls -l /dev/hidraw* /dev/input/by-id
        for node in /dev/hidraw*; do
            [ -c "$node" ] || continue
            run udevadm info --query=property --name="$node"
            run getfacl "$node"
        done
        if [ -n "$audio_uid" ] && [ "$audio_uid" != 0 ] && [ -n "$audio_home" ]; then
            run_audio sh -c '
                for node in /dev/hidraw*; do
                    [ -c "$node" ] || continue
                    printf "%s: " "$node"
                    if [ -r "$node" ]; then printf "readable "; else printf "not-readable "; fi
                    if [ -w "$node" ]; then printf "writable\n"; else printf "not-writable\n"; fi
                done'
        fi
    } >"$report/$phase-access.txt" 2>&1
}

printf 'Install this update and reboot before capturing.\n'
printf 'For audio, pair the headset and choose its profile in KDE first.\n'
if [ "$interactive" = 1 ]; then
    prompt 'Unplug the test device from the right-hand USB-C port.'
    sleep 5
    snapshot 01-unplugged
    prompt 'Plug the YubiKey 5C or thumb drive directly into the right-hand USB-C port.'
    sleep 5
    snapshot 02-connected
    prompt 'Unplug the same device from the right-hand USB-C port.'
    sleep 5
    snapshot 03-unplugged-again
    prompt 'Turn the same USB-C plug over and reconnect it directly to the right-hand port.'
    sleep 5
    snapshot 04-connected-flipped
    prompt 'Unplug the same device from the right-hand USB-C port again.'
    sleep 5
    snapshot 05-unplugged-final
else
    snapshot 01-current-state
fi

{
    run rfkill list
    run systemctl --no-pager --full status bluetooth.service
    run journalctl --no-pager -b -u bluetooth.service
    run bluetoothctl --version
    run bluetoothctl list
    run bluetoothctl show
    run bluetoothctl devices Paired
    run bluetoothctl devices Connected
    if command -v bluetoothctl >/dev/null 2>&1; then
        devices=$(timeout -k 2s 15s bluetoothctl devices Paired 2>&1) || devices=
        for address in $(printf '%s\n' "$devices" | awk '$1 == "Device" && $2 ~ /^[0-9A-Fa-f:]+$/ {print $2}'); do
            run bluetoothctl info "$address"
        done
    fi
} >"$report/bluetooth-system.txt" 2>&1

{
    printf 'Desktop user: %s\nRuntime UID: %s\n' "$audio_user" "$audio_uid"
    if [ -n "$audio_uid" ] && [ "$audio_uid" != 0 ] && [ -n "$audio_home" ] &&
        [ -S "/run/user/$audio_uid/bus" ]; then
        run ls -l "/run/user/$audio_uid/bus" "/run/user/$audio_uid/pipewire-0" "/run/user/$audio_uid/pulse/native"
        run_audio systemctl --user --no-pager --full status pipewire pipewire-pulse wireplumber
        run_audio journalctl --user --no-pager -b -u pipewire -u pipewire-pulse -u wireplumber
        run_audio wpctl status
        run_audio pw-dump
        run_audio pactl list cards
        run_audio pactl list sinks
        run_audio pactl list sources
    else
        printf 'No desktop session bus for the selected user.\n'
        printf 'Run through sudo from Alice in KDE, or supply --user alice.\n'
    fi
} >"$report/bluetooth-audio.txt" 2>&1

{
    run cat /proc/bus/input/devices /proc/asound/cards /proc/asound/pcm
    run ls -l /dev/dri /dev/snd /dev/video*
    for log in "$audio_home"/.local/share/xorg/Xorg.*.log /var/log/Xorg.*.log; do
        [ -n "$audio_home" ] && [ -f "$log" ] || continue
        run cat "$log"
    done
} >"$report/input-display-audio.txt" 2>&1
printf 'Collection complete at ' >"$report/COMPLETE.txt"
date -u +%Y-%m-%dT%H:%M:%SZ >>"$report/COMPLETE.txt"
rm "$report/INCOMPLETE.txt"
archive_temporary=$(mktemp "$report.tar.gz.partial.XXXXXX")
tar -czf "$archive_temporary" -C "${report%/*}" "${report##*/}"
mv "$archive_temporary" "$report.tar.gz"
archive_temporary=
sync || { printf 'Files saved, but flushing them to disk failed.\n' >&2; exit 1; }
printf '\nSaved diagnostics: %s.tar.gz\n' "$report"
printf 'Bring that archive back to macOS. Unavailable optional commands are logged inside.\n'
