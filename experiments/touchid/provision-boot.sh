#!/bin/sh
# SPDX-License-Identifier: MIT
# Attended J614s enrollment trial: restore boot pair, then provision with guard.
set -u
[ "$(uname -r)" = 7.3.0-m4rch-touchid-ro ] || exit 0
cmdline=" $(cat /proc/cmdline) "
case "$cmdline" in *' m4rch_touchid=enroll '*) ;; *) exit 0 ;; esac
case "$cmdline" in *' apple_sep.xart_writes='*|*' apple_sep.provision_keybag='*|*' apple_sep.xart_guard='*) exit 1 ;; esac
umask 077
state=/var/lib/m4rch-touchid-diagnostic
mkdir -p "$state"
log="$state/enroll-$(cat /proc/sys/kernel/random/boot_id).log"
exec >"$log" 2>&1
printf 'Kernel: '; uname -r
printf 'Boot ID: '; cat /proc/sys/kernel/random/boot_id
if ! cmp -s /boot/boot.bin /boot/.boot-m4rch-touchid-ro.bin || \
   ! cmp -s /boot/grub/grub.cfg /boot/grub/grub-touchid-provision.cfg; then
  echo 'Active boot pair changed; refusing provisioning'; exit 1
fi
if ! cp /boot/.boot-before-touchid.bin /boot/.boot-touchid-restore.tmp || \
   ! cmp -s /boot/.boot-before-touchid.bin /boot/.boot-touchid-restore.tmp || \
   ! cp /boot/grub/grub-before-touchid.cfg /boot/grub/.touchid-restore.tmp || \
   ! cmp -s /boot/grub/grub-before-touchid.cfg /boot/grub/.touchid-restore.tmp || \
   ! mv -f /boot/.boot-touchid-restore.tmp /boot/boot.bin || \
   ! mv -f /boot/grub/.touchid-restore.tmp /boot/grub/grub.cfg; then
  echo 'Boot pair restore failed; refusing provisioning'; exit 1
fi
sync
cmp -s /boot/boot.bin /boot/.boot-before-touchid.bin && \
cmp -s /boot/grub/grub.cfg /boot/grub/grub-before-touchid.cfg || exit 1
echo 'Previous boot pair restored'
[ ! -d /sys/module/apple_sep ] || { echo 'SEP already loaded; refusing'; exit 1; }
[ ! -e /var/lib/aurora-sep-keybag.bin ] || { echo 'Existing keybag; refusing fresh provisioning'; exit 1; }
private=/home/michal/Projects/m4rch/cache/touchid-candidate/private-inputs
[ -d "$private" ] || { echo 'Private inputs and backup missing'; exit 1; }
for name in msrk-j614s.bin mesacal-j614s.bin; do
  [ "$(stat -c %u:%g:%a /usr/lib/firmware/apple/$name)" = 0:0:600 ] || exit 1
  cmp -s "/usr/lib/firmware/apple/$name" "$private/$name" || { echo 'Sensor input changed'; exit 1; }
done
(cd "$private" && sha256sum -c iboot-container-before-sep.img.sha256) || {
  echo 'Pretrial iBoot snapshot does not verify'; exit 1;
}
for p in local-policy-manifest iboot-manifest; do
  [ -s "/sys/firmware/devicetree/base/sep@406600000/$p" ] || { echo "$p absent"; exit 1; }
done
echo 'Checking APFS xART metadata before provisioning'
/usr/bin/python3 /usr/local/libexec/m4rch-touchid-verify-xart || exit 1
echo 'Loading SEP with xART writes and keybag provisioning enabled; guard forced to 1'
timeout 200s /usr/local/libexec/m4rch-touchid-sep-load
rc=$?
echo "SEP loader exit: $rc"
if [ "$rc" -eq 0 ]; then
  timeout 100s /usr/bin/python3 /usr/local/libexec/m4rch-touchid-sensor-present
  echo "Sensor-present exit: $?"
fi
for name in profile attach boot endpoints keybag keystore matching sensor sensor_attach touchid restore xart xart_guard xart_guard_list xart_guard_refusals; do
  file="/sys/bus/platform/devices/406600000.sep/diag/$name"
  if [ -r "$file" ]; then printf '%s: ' "$name"; cat "$file"; fi
done
journalctl -k -b --no-pager -o short-monotonic | grep -iE 'apple_sep|xart|touch.?id|sensor:|sbio:|sks:|mesa' || true
exit "$rc"
