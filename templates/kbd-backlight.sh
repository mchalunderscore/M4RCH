#!/bin/sh
# Control only the built-in keyboard backlight. Run writes through sudo.
set -eu
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH

led=/sys/class/leds/kbd_backlight

fail()
{
    printf 'm4rch-kbd-backlight: %s\n' "$*" >&2
    exit 1
}

usage()
{
    printf 'Usage: m4rch-kbd-backlight status|up|down|off|PERCENT\n'
    printf 'PERCENT is an integer from 0 to 100; up/down change by about 10%%.\n'
}

[ "$#" -eq 1 ] || { usage >&2; exit 2; }
case $1 in
    --help|-h) usage; exit 0 ;;
    status|up|down|off|0|[1-9]|[1-9][0-9]|100) action=$1 ;;
    *) usage >&2; exit 2 ;;
esac

[ -d "$led" ] || fail "Keyboard backlight device is missing: $led"
maximum=$(cat "$led/max_brightness") || fail 'Cannot read maximum brightness.'
current=$(cat "$led/brightness") || fail 'Cannot read current brightness.'
# Sysfs supplies decimal integers. Reject malformed values before arithmetic.
for value in "$maximum" "$current"; do
    case $value in
        ''|*[!0-9]*|0[0-9]*) fail 'Invalid brightness value from the kernel.' ;;
    esac
    [ "${#value}" -le 6 ] || fail 'Brightness value is out of range.'
done
[ "$maximum" -gt 0 ] || fail 'Maximum brightness must be positive.'
[ "$current" -le "$maximum" ] || fail 'Current brightness exceeds the maximum.'

case $action in
    status)
        printf '%s/%s (%s%%)\n' "$current" "$maximum" "$((current * 100 / maximum))"
        exit 0
        ;;
    up) target=$((current + (maximum + 9) / 10)) ;;
    down) target=$((current - (maximum + 9) / 10)) ;;
    off) target=0 ;;
    *) target=$(((maximum * action + 50) / 100)) ;;
esac
[ "$target" -le "$maximum" ] || target=$maximum
[ "$target" -ge 0 ] || target=0
if ! printf '%s\n' "$target" > "$led/brightness"; then
    fail 'Cannot set keyboard brightness; run this command with sudo.'
fi
