#!/bin/sh
# SPDX-License-Identifier: MIT
# Enrollment sequence based on Asahi Linux's step2.sh at
# c53d66dc71937efa2530d4323c81addaebb5a09b. See third_party/ASAHI-LICENSE.
# This is a template: the host builder replaces the strictly validated markers.
# No Python, shell evaluation of a manifest, or password arguments are required.
set -eu
PATH=/usr/bin:/bin:/usr/sbin:/sbin
LC_ALL=C
export PATH LC_ALL
umask 077

VGID='##VGID##'
SYSTEM_UUID='##SYSTEM_UUID##'
DATA_UUID='##DATA_UUID##'
PREBOOT_UUID='##PREBOOT_UUID##'
RECOVERY_UUID='##RECOVERY_UUID##'
STORE_UUID='##STORE_UUID##'
PLATFORM_UUID='##PLATFORM_UUID##'
SOURCE_MACOS_VGID='##SOURCE_MACOS_VGID##'
SOURCE_MACOS_STORE_UUID='##SOURCE_MACOS_STORE_UUID##'
BOOT_SHA256='##BOOT_SHA256##'
PREVIOUS_BOOT_SHA256='##PREVIOUS_BOOT_SHA256##'
BOOT_BYTES='##BOOT_BYTES##'
AUTO_LAUNCH='##AUTO_LAUNCH##'
INITIAL_ENROLLMENT='##INITIAL_ENROLLMENT##'
OWNER_SHA256='##OWNER_SHA256##'
SYSTEM_VERSION_SHA256='##SYSTEM_VERSION_SHA256##'
INSTALLER_SHA256='##INSTALLER_SHA256##'
APP_INFO_SHA256='##APP_INFO_SHA256##'
APP_LAUNCHER_SHA256='##APP_LAUNCHER_SHA256##'

die() { printf '%s\n' "m4rch: $*" >&2; exit 1; }
plist() { /usr/libexec/PlistBuddy -c "Print :$2" "$1" 2>/dev/null; }
same() { [ "$1" = "$2" ] || die "$3 mismatch (expected $2, found $1)."; }
uuid() {
    printf '%s\n' "$1" | grep -Eq '^[A-F0-9]{8}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{12}$' ||
        die 'Invalid or unrendered UUID in this enrollment script.'
}
info() { diskutil info -plist "$1" > "$work/$2.plist" || die "Cannot inspect $1."; }
check_volume() {
    # $1 = expected UUID, $2 = expected APFS role. No device names are persisted.
    info "$1" "$2"
    same "$(plist "$work/$2.plist" VolumeUUID)" "$1" "$2 volume UUID"
    same "$(plist "$work/$2.plist" APFSContainerReference)" "$container" "$2 container"
    index=0
    found=0
    while candidate=$(plist "$work/apfs.plist" "Containers:0:Volumes:$index:APFSVolumeUUID"); do
        if [ "$candidate" = "$1" ]; then
            same "$(plist "$work/apfs.plist" "Containers:0:Volumes:$index:Roles:0")" "$2" "$2 role"
            if plist "$work/apfs.plist" "Containers:0:Volumes:$index:Roles:1" >/dev/null; then
                die "$2 volume unexpectedly has multiple roles."
            fi
            found=$((found + 1))
        fi
        index=$((index + 1))
    done
    same "$found" 1 "$2 identity count"
}
digest_file() {
    command -v sha256 >/dev/null 2>&1 || die 'Recovery is missing sha256; cannot verify files.'
    digest=$(sha256 -q "$1") || die "Cannot calculate SHA-256 for $1."
    printf '%s\n' "$digest" | grep -Eq '^[a-f0-9]{64}$' || die "Invalid SHA-256 output for $1."
}
check_bundle() {
    [ -f "$bundle" ] && [ ! -L "$bundle" ] || die 'Boot object is missing or is a symlink.'
    same "$(wc -c < "$bundle" | tr -d '[:space:]')" "$BOOT_BYTES" 'Boot object byte count'
    digest_file "$bundle"
    same "$digest" "$BOOT_SHA256" 'Boot object SHA-256'
}

checked_file() {
    [ -f "$1" ] && [ ! -L "$1" ] || die "$3 is missing, is not regular, or is a symlink."
    digest_file "$1"
    same "$digest" "$2" "$3 SHA-256"
}
metadata_pair() {
    # Exactly one pathname must exist. Both names carry identical bound bytes.
    count=0
    selected=
    for candidate_path in "$1" "$2"; do
        if [ -e "$candidate_path" ] || [ -L "$candidate_path" ]; then
            checked_file "$candidate_path" "$3" "$4"
            selected=$candidate_path
            count=$((count + 1))
        fi
    done
    same "$count" 1 "$4 file count"
}
check_metadata() {
    for directory in "$system_dir/System" "$system_dir/System/Library" "$core"; do
        [ -d "$directory" ] && [ ! -L "$directory" ] || die 'Invalid System metadata directory.'
    done
    if [ "$AUTO_LAUNCH" = 1 ]; then
        metadata_pair "$core/SystemVersion.plist" "$core/SystemVersion-disabled.plist" \
            "$SYSTEM_VERSION_SHA256" 'System version metadata'
        version_file=$selected
        metadata_pair "$system_dir/.IAPhysicalMedia" "$system_dir/IAPhysicalMedia-disabled.plist" \
            "$INSTALLER_SHA256" 'Installer marker'
        installer_file=$selected
        [ -d "$contents/MacOS" ] && [ ! -L "$contents/MacOS" ] || die 'Invalid enrollment app executable directory.'
        checked_file "$contents/Info.plist" "$APP_INFO_SHA256" 'Enrollment app Info.plist'
        checked_file "$contents/MacOS/launch.sh" "$APP_LAUNCHER_SHA256" 'Enrollment app launcher'
    else
        [ -f "$core/SystemVersion.plist" ] && [ ! -L "$core/SystemVersion.plist" ] ||
            die 'Enrolled System metadata is missing or is a symlink.'
        [ ! -e "$core/SystemVersion-disabled.plist" ] && [ ! -L "$core/SystemVersion-disabled.plist" ] ||
            die 'Unexpected hidden System metadata in manual enrollment mode.'
        [ ! -e "$system_dir/.IAPhysicalMedia" ] && [ ! -L "$system_dir/.IAPhysicalMedia" ] ||
            die 'Unexpected installer marker on enrolled system.'
    fi
}
check_receipt() {
    if [ "$INITIAL_ENROLLMENT" = 1 ] && [ ! -e "$receipt" ] && [ ! -L "$receipt" ]; then
        receipt_hash=
        return 0
    fi
    [ -f "$receipt" ] && [ ! -L "$receipt" ] || die 'Missing previous enrollment receipt.'
    same "$(sed -n '1p' "$receipt")" "$VGID" 'Enrollment receipt volume group'
    same "$(wc -l < "$receipt" | tr -d '[:space:]')" 2 'Enrollment receipt line count'
    [ -z "$(sed -n '3p' "$receipt")" ] || die 'Unexpected data in enrollment receipt.'
    receipt_hash=$(sed -n '2p' "$receipt")
    case "$receipt_hash" in
        "$PREVIOUS_BOOT_SHA256"|"$BOOT_SHA256") ;;
        *) die 'Enrollment receipt no longer matches this staged update.' ;;
    esac
}
finish_metadata() {
    [ "$AUTO_LAUNCH" = 1 ] || return 0
    check_metadata
    if [ "$version_file" = "$core/SystemVersion.plist" ] &&
       [ "$installer_file" = "$system_dir/IAPhysicalMedia-disabled.plist" ]; then
        return 0
    fi
    check_receipt
    same "$receipt_hash" "$BOOT_SHA256" 'Completed enrollment receipt'
    # A prior invocation may have stopped after replacing the receipt but
    # before syncing it. Re-establish durability before resuming cleanup.
    sync
    mount -u -w "$system_dir" || die 'Cannot make System metadata writable.'
    # The durable receipt must precede either picker-metadata change. If power
    # is lost between these moves, the next invocation resumes without kmutil.
    if [ "$version_file" != "$core/SystemVersion.plist" ]; then
        mv "$version_file" "$core/SystemVersion.plist" || die 'Cannot restore System version metadata.'
    fi
    if [ "$installer_file" != "$system_dir/IAPhysicalMedia-disabled.plist" ]; then
        mv "$installer_file" "$system_dir/IAPhysicalMedia-disabled.plist" || die 'Cannot disable installer marker.'
    fi
    sync
    check_metadata
}
offer_reboot() {
    [ "$AUTO_LAUNCH" = 1 ] || return 0
    # A disconnected launcher, redirected input, or EOF never reboots the Mac.
    [ -t 0 ] && [ -t 1 ] || return 0
    printf '\n%s' 'Reboot now? [y/N] '
    IFS= read -r answer || return 0
    case "$answer" in y|Y|yes|YES|Yes) sync; reboot ;; esac
}

mode=update
[ "$INITIAL_ENROLLMENT" = 0 ] || mode=enroll
case $# in
    0) ;;
    1) case $1 in
        --update) mode=update ;;
        --enroll) mode=enroll ;;
        --check) mode=check ;;
        --help) printf '%s\n' 'Usage: sh enroll.sh [--check|--enroll|--update]' \
            'Run in paired One True Recovery for this Arch installation.' \
            '--check validates without mounting, changing policy, or enrolling.'; exit 0 ;;
        *) die 'Expected --check, --enroll or --update.' ;;
    esac ;;
    *) die 'Too many arguments.' ;;
esac

for value in "$VGID" "$SYSTEM_UUID" "$DATA_UUID" "$PREBOOT_UUID" "$RECOVERY_UUID" \
    "$STORE_UUID" "$PLATFORM_UUID" "$SOURCE_MACOS_VGID" "$SOURCE_MACOS_STORE_UUID"; do
    uuid "$value"
done
[ "$VGID" != "$SOURCE_MACOS_VGID" ] || die 'Refusing the original macOS volume group.'
[ "$STORE_UUID" != "$SOURCE_MACOS_STORE_UUID" ] || die 'Refusing the original macOS APFS physical store.'
printf '%s\n' "$PREVIOUS_BOOT_SHA256" | grep -Eq '^[a-f0-9]{64}$' || die 'Invalid previous boot digest.'
printf '%s\n' "$BOOT_SHA256" | grep -Eq '^[a-f0-9]{64}$' || die 'Invalid boot digest.'
case $BOOT_BYTES in ''|*[!0-9]*) die 'Invalid boot object size.' ;; esac
[ "$BOOT_BYTES" -gt 0 ] || die 'Empty boot object.'
printf '%s\n' "$OWNER_SHA256" | grep -Eq '^[a-f0-9]{64}$' || die 'Invalid first-enrollment owner digest.'
case $INITIAL_ENROLLMENT in 0|1) ;; *) die 'Invalid first-enrollment mode.' ;; esac
case $mode in
    enroll) [ "$INITIAL_ENROLLMENT" = 1 ] || die 'This is an update script; use --update.' ;;
    update) [ "$INITIAL_ENROLLMENT" = 0 ] || die 'First enrollment requires --enroll.' ;;
esac
case $AUTO_LAUNCH in 0|1) ;; *) die 'Invalid automatic launcher mode.' ;; esac
for value in "$SYSTEM_VERSION_SHA256" "$INSTALLER_SHA256" "$APP_INFO_SHA256" "$APP_LAUNCHER_SHA256"; do
    printf '%s\n' "$value" | grep -Eq '^[a-f0-9]{64}$' || die 'Invalid automatic enrollment metadata digest.'
done
same "$(uname -s)" Darwin 'Operating system'
same "$(uname -m)" arm64 'Architecture'
same "$(sysctl -n hw.model)" Mac16,8 'Mac model'
same "$(id -u)" 0 'Effective user (run from Recovery Terminal)'

work=$(mktemp -d /tmp/arch-m4-enroll.XXXXXX) || die 'Cannot create private temporary directory.'
receipt_tmp=
trap 'if [ -n "$receipt_tmp" ]; then rm -f "$receipt_tmp"; fi; rm -rf "$work"' 0
trap 'exit 1' 1 2 3 15
ioreg -a -r -d 1 -c IOPlatformExpertDevice > "$work/platform.plist"
same "$(plist "$work/platform.plist" 0:IOPlatformUUID)" "$PLATFORM_UUID" 'Mac identity'

info "$SYSTEM_UUID" System
same "$(plist "$work/System.plist" VolumeUUID)" "$SYSTEM_UUID" 'System volume UUID'
same "$(plist "$work/System.plist" APFSVolumeGroupID)" "$VGID" 'System volume group'
container=$(plist "$work/System.plist" APFSContainerReference) || die 'Missing APFS container.'
system_dir=$(plist "$work/System.plist" MountPoint) || die "Mount System volume $SYSTEM_UUID in Disk Utility first."
case $system_dir in /Volumes/*) ;; *) die 'System volume is not mounted below /Volumes.' ;; esac
[ -d "$system_dir" ] && [ ! -L "$system_dir" ] || die 'Invalid System mount point.'
diskutil apfs list "$container" -plist > "$work/apfs.plist"
same "$(plist "$work/apfs.plist" Containers:0:ContainerReference)" "$container" 'APFS container'
if plist "$work/apfs.plist" Containers:1 >/dev/null; then die 'Ambiguous APFS container.'; fi
same "$(plist "$work/apfs.plist" Containers:0:PhysicalStores:0:DiskUUID)" "$STORE_UUID" 'Boot-stub APFS partition UUID'
if plist "$work/apfs.plist" Containers:0:PhysicalStores:1 >/dev/null; then
    die 'Multiple physical stores are not supported.'
fi
store=$(plist "$work/apfs.plist" Containers:0:PhysicalStores:0:DeviceIdentifier)
info "$store" store
same "$(plist "$work/store.plist" DiskUUID)" "$STORE_UUID" 'Physical store UUID'
whole=$(plist "$work/store.plist" ParentWholeDisk)
info "$whole" whole
same "$(plist "$work/whole.plist" WholeDisk)" true 'Physical whole disk'
same "$(plist "$work/whole.plist" Internal)" true 'Internal boot-stub disk'
same "$(plist "$work/whole.plist" RemovableMediaOrExternalDevice)" false 'Non-removable internal disk'
same "$(plist "$work/whole.plist" Ejectable)" false 'Non-ejectable internal disk'
same "$(plist "$work/whole.plist" BusProtocol)" 'Apple Fabric' 'Internal NVMe bus'
# diskutil reports Unknown for the built-in Apple ANS controller. Its exact
# bus/controller path and non-removable properties establish the transport.
case $(plist "$work/whole.plist" VirtualOrPhysical) in
    Physical|Unknown) ;;
    *) die 'The internal boot stub is on virtual media.' ;;
esac
case $(plist "$work/whole.plist" DeviceTreePath) in
    IODeviceTree:*/ans@*/iop-ans-nub/AppleANS*Controller) ;;
    *) die 'The internal boot stub is not on the built-in NVMe controller.' ;;
esac
if plist "$work/apfs.plist" Containers:0:Volumes:4 >/dev/null; then
    die 'The internal boot-stub container contains additional volumes.'
fi

check_volume "$SYSTEM_UUID" System
check_volume "$DATA_UUID" Data
check_volume "$PREBOOT_UUID" Preboot
check_volume "$RECOVERY_UUID" Recovery
same "$(plist "$work/Data.plist" APFSVolumeGroupID)" "$VGID" 'Data volume group'
contents="$system_dir/Finish Installation.app/Contents"
resources="$contents/Resources"
bundle="$resources/boot.bin"
receipt="$resources/enrolled.txt"
core="$system_dir/System/Library/CoreServices"
for directory in "$system_dir/Finish Installation.app" "$system_dir/Finish Installation.app/Contents" "$resources"; do
    [ -d "$directory" ] && [ ! -L "$directory" ] || die 'Invalid loader resource directory.'
done
[ ! -L "$receipt.new" ] || die 'Unexpected symlink at the receipt staging path.'

bputil -d -v "$VGID" > "$work/policy.txt" || die 'Cannot read the installation boot policy.'
cat "$work/policy.txt"
if grep -Eq '^[[:space:]]*(OS Type[[:space:]]*|Current OS environment):[[:space:]]*macOS[[:space:]]*$' "$work/policy.txt"; then
    die 'Running in ordinary macOS. Open Utilities > Terminal while still in Recovery, after authenticating with Macintosh HD. This output cannot establish Recovery pairing.'
fi
grep -Eq ':[[:space:]]*Paired([[:space:]]|$)' "$work/policy.txt" ||
    die 'Wrong paired Recovery for this Arch installation. Stop: selecting its entry inside an already running Recovery does not change pairing. Startup selection must succeed before its paired Recovery can start.'
grep -Fq 'one true recoveryOS' "$work/policy.txt" ||
    die 'Not One True Recovery: shut down fully and hold power continuously; do not double-press.'

check_bundle
check_receipt
check_metadata

printf '\n%s\n' "Verified $mode target: $system_dir" "Volume group: $VGID" \
    "Boot disk: $whole; APFS partition: $STORE_UUID" "Boot SHA-256: $BOOT_SHA256"
# Mount only the already verified boot-stub Preboot volume. This does not alter
# the installation's boot policy; all enrollment mutations are below the prompt.
if [ "$mode" != check ]; then diskutil mount "$PREBOOT_UUID"; fi
info "$PREBOOT_UUID" Preboot
same "$(plist "$work/Preboot.plist" VolumeUUID)" "$PREBOOT_UUID" 'Mounted Preboot UUID'
preboot=$(plist "$work/Preboot.plist" MountPoint) || die "Mount Preboot volume $PREBOOT_UUID in Disk Utility first."
case $preboot in /Volumes/*) ;; *) die 'Preboot is not mounted below /Volumes.' ;; esac
for directory in "$preboot" "$preboot/$VGID" "$preboot/$VGID/var" "$preboot/$VGID/var/db"; do
    [ -d "$directory" ] && [ ! -L "$directory" ] || die 'Invalid boot-stub owner metadata directory.'
done
owner="$preboot/$VGID/var/db/AdminUserRecoveryInfo.plist"
[ -f "$owner" ] && [ ! -L "$owner" ] || die 'Missing copied owner recovery information.'
plutil -lint "$owner" >/dev/null || die 'Invalid owner recovery information.'
if [ "$INITIAL_ENROLLMENT" = 1 ]; then
    digest_file "$owner"
    same "$digest" "$OWNER_SHA256" 'First-enrollment owner metadata'
fi
if [ "$mode" = check ]; then
    printf '%s\n' 'Read-only enrollment preflight passed. No boot policy or files were changed.'
    exit 0
fi

if [ "$receipt_hash" = "$BOOT_SHA256" ]; then
    finish_metadata
    printf '%s\n' 'This fixed SD loader is already enrolled; picker metadata is complete.'
    offer_reboot
    exit 0
fi

printf '\n%s\n' 'This changes only the verified Arch installation policy and its boot object.'
printf '%s' 'Continue? [y/N] '
IFS= read -r answer || die 'Cancelled.'
case "$answer" in y|Y|yes|YES|Yes) ;; *) die 'Cancelled.' ;; esac
check_bundle
check_receipt
check_metadata

# Apple's tools request the existing owner credentials; no passwords in argv.
# Only a new installation needs its first permissive/custom-boot policy.
if [ "$mode" = enroll ] && [ -z "$receipt_hash" ]; then
    bputil -nc -v "$VGID" || die 'Initial policy authorization failed; no loader was enrolled.'
fi
if [ "$receipt_hash" != "$BOOT_SHA256" ]; then
    kmutil configure-boot -c "$bundle" --raw --entry-point 2048 \
        --lowest-virtual-address 0 -v "$system_dir" ||
        die 'Kernel enrollment failed. Retry from its paired Recovery; the script has not switched its picker metadata.'

    mount -u -w "$system_dir" || die 'Cannot make the enrollment receipt writable.'
    receipt_tmp=$(mktemp "$resources/.enrolled.XXXXXX") || die 'Cannot create atomic enrollment receipt.'
    printf '%s\n%s\n' "$VGID" "$BOOT_SHA256" > "$receipt_tmp"
    mv "$receipt_tmp" "$receipt" || die 'Cannot record completed enrollment.'
    receipt_tmp=
    sync
fi
finish_metadata
printf '\n%s\n' 'Enrollment completed. Quit Terminal, shut down, then hold power and select this Arch installation.' \
    'The loader reads the SD card at boot. Later SD payload updates do not need enrollment.'
offer_reboot
