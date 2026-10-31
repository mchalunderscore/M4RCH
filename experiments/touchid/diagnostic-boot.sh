#!/bin/sh
# SPDX-License-Identifier: MIT
# One-time read-only SEP diagnostic; installed root-owned for the trial boot.
set -u
[ "$(uname -r)" = 7.3.0-m4rch-touchid-ro ] || exit 0
cmdline=" $(cat /proc/cmdline) "
case "$cmdline" in *' apple_sep.xart_writes=0 '*) ;; *) exit 1 ;; esac
case "$cmdline" in *' apple_sep.provision_keybag=0 '*) ;; *) exit 1 ;; esac
umask 077
state=/var/lib/m4rch-touchid-diagnostic
mkdir -p "$state"
log="$state/$(cat /proc/sys/kernel/random/boot_id).log"
exec >"$log" 2>&1
printf 'Kernel: '; uname -r
printf 'Boot ID: '; cat /proc/sys/kernel/random/boot_id
printf 'Reverting boot selection: '
if cmp -s /boot/boot.bin /boot/.boot-m4rch-touchid-ro.bin && \
   cmp -s /boot/grub/grub.cfg /boot/grub/grub-touchid-diagnostic.cfg && \
   [ -s /boot/.boot-before-touchid.bin ] && [ -s /boot/grub/grub-before-touchid.cfg ]; then
  if cp /boot/.boot-before-touchid.bin /boot/.boot-touchid-restore.tmp && \
     cmp -s /boot/.boot-before-touchid.bin /boot/.boot-touchid-restore.tmp && \
     cp /boot/grub/grub-before-touchid.cfg /boot/grub/.touchid-restore.tmp && \
     cmp -s /boot/grub/grub-before-touchid.cfg /boot/grub/.touchid-restore.tmp && \
     mv -f /boot/.boot-touchid-restore.tmp /boot/boot.bin && \
     mv -f /boot/grub/.touchid-restore.tmp /boot/grub/grub.cfg; then
    sync
    echo 'restored previous boot pair'
  else
    echo 'FAILED, inspect boot files before rebooting'
  fi
else
  echo 'skipped: active pair changed or backup missing'
fi
for p in local-policy-manifest iboot-manifest; do
  path="/sys/firmware/devicetree/base/sep@406600000/$p"
  if [ -s "$path" ]; then printf '%s: present (%s bytes)\n' "$p" "$(wc -c <"$path")"; else printf '%s: missing\n' "$p"; fi
done
printf 'SEP module load (read-only xART):\n'
timeout 150s modprobe --first-time apple_sep
rc=$?
printf 'modprobe exit: %s\n' "$rc"
printf 'SEP biometric node: '; [ -c /dev/sep-bio ] && echo present || echo absent
printf 'Relevant kernel log:\n'
journalctl -k -b --no-pager -o short-monotonic | grep -iE 'apple.sep|xart|touch.?id|mesa|sbio|sks|gigalocker|sep@' || true
printf 'Diagnostic complete\n'
exit "$rc"
