#!/bin/sh
# Target-specific repair for the staged J614s 25G83 firmware transaction.
set -eu
VGID=05F89AF0-EFD8-44CB-ABEB-D805D7B34F63
SYSTEM_UUID=AE094BB5-7339-4064-B333-9A2FA99108ED
BOOT_SHA=7be71259bcf1fc8e3a66d80f59b597e8d9c30104206362ac193845273a2953c8
fail() { printf '%s\n' "$*" >&2; exit 1; }
for tool in id mktemp bputil diskutil cat grep sha256 bless; do
    command -v "$tool" >/dev/null 2>&1 || fail "Recovery is missing $tool. No policy changed."
done
[ -x /usr/libexec/PlistBuddy ] || fail 'Recovery is missing PlistBuddy. No policy changed.'
[ "$(id -u)" = 0 ] || fail 'Run from Recovery Utilities > Terminal (root).'
work=$(mktemp -d /tmp/m4rch-policy.XXXXXX)
# Leave the small policy/identity capture behind if this fails.
printf 'Diagnostic files: %s\n' "$work"
bputil -d -v "$VGID" > "$work/policy-before.txt"
cat "$work/policy-before.txt"
grep -Fq 'one true recoveryOS' "$work/policy-before.txt" ||
    fail 'Not One True Recovery. Do not change policy; photograph the output above.'
diskutil mount "$SYSTEM_UUID"
diskutil info -plist "$SYSTEM_UUID" > "$work/system.plist"
plist() { /usr/libexec/PlistBuddy -c "Print :$2" "$1"; }
[ "$(plist "$work/system.plist" VolumeUUID)" = "$SYSTEM_UUID" ] || fail 'Wrong System volume UUID.'
[ "$(plist "$work/system.plist" APFSVolumeGroupID)" = "$VGID" ] || fail 'Wrong volume group.'
system=$(plist "$work/system.plist" MountPoint)
case "$system" in /Volumes/*) ;; *) fail 'Unexpected System mount path.' ;; esac
[ ! -L "$system" ] || fail 'Unexpected mount symlink.'
resources="$system/Finish Installation.app/Contents/Resources"
[ -f "$resources/boot.bin" ] && [ ! -L "$resources/boot.bin" ] || fail 'Missing stage 1.'
actual=$(sha256 -q "$resources/boot.bin") || fail 'Cannot hash stage 1.'
printf '%s\n' "$actual" | grep -Eq '^[a-f0-9]{64}$' || fail 'Invalid SHA-256 output.'
[ "$actual" = "$BOOT_SHA" ] || fail 'Stage 1 differs from the verified working loader.'
version="$system/System/Library/CoreServices/SystemVersion.plist"
[ "$(plist "$version" ProductBuildVersion)" = 25G83 ] || fail 'Expected the staged 25G83 Apple stub.'
printf '\n%s\n' 'Recreate only M4RCH policy as Reduced Security, then personalize/select its staged Apple firmware.' \
    'M4RCH will need custom-boot enrollment again before Linux can boot. Primary macOS policy is not targeted.'
printf '%s' 'Type REPAIR M4RCH: '
IFS= read -r answer
[ "$answer" = 'REPAIR M4RCH' ] || fail 'Cancelled.'
bputil -g -v "$VGID" || fail 'Reduced policy recreation failed; stop and photograph the error.'
bputil -d -v "$VGID" > "$work/policy-reduced.txt"
bless --setBoot --mount "$system" || fail 'Apple startup personalization failed; stop and photograph the error.'
printf '\n%s\n' 'Startup personalization succeeded. Shut down completely, then hold power and enter Options again.' \
    'This second Recovery entry must pair with the selected M4RCH installation. Run:'
printf 'sh "%s/enroll.sh" --update\n' "$resources"
printf '%s\n' 'The existing enrollment script checks pairing, restores permissive custom boot and enrolls stage 1.' \
    'After successful enrollment, return to macOS and run sudo make stub-finish.'
