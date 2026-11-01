#!/bin/bash
set -euo pipefail
dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
[[ $EUID == 0 ]] || { echo 'Run this script with sudo.' >&2; exit 1; }
[[ $(uname -r) == *m4rch* && -f /etc/mkinitcpio-m4rch.conf && -f /boot/initramfs-linux-m4rch.img ]] || {
  echo 'This does not look like the booted M4RCH installation; stopping.' >&2; exit 1;
}
cd "$dir"
sha256sum -c SHA256SUMS
install -d -m 0755 /usr/lib/firmware/brcm
for file in brcm/*; do install -m 0644 "$file" "/usr/lib/firmware/brcm/${file##*/}"; done
config=/etc/mkinitcpio-m4rch.conf
include=/etc/mkinitcpio-m4rch-wifi.conf
backup=/boot/initramfs-linux-m4rch.img.pre-wifi
if [[ ! -e $backup ]]; then cp -p /boot/initramfs-linux-m4rch.img "$backup"; fi
if [[ ! -e ${config}.pre-wifi ]]; then cp -p "$config" "${config}.pre-wifi"; fi
{
  printf 'FILES+=('
  for file in brcm/*; do printf ' %q' "/usr/lib/firmware/brcm/${file##*/}"; done
  printf ' )\n'
} > "$include"
if ! grep -Fxq '. /etc/mkinitcpio-m4rch-wifi.conf' "$config"; then
  printf '\n. /etc/mkinitcpio-m4rch-wifi.conf\n' >> "$config"
fi
if ! mkinitcpio -p linux-m4rch; then
  cp -p "$backup" /boot/initramfs-linux-m4rch.img
  echo 'Initramfs rebuild failed; restored the pre-repair image.' >&2
  exit 1
fi
if ! listing=$(lsinitcpio /boot/initramfs-linux-m4rch.img); then
  cp -p "$backup" /boot/initramfs-linux-m4rch.img
  echo 'Cannot inspect the rebuilt initramfs; restored the previous image.' >&2
  exit 1
fi
for file in brcm/*; do
  [[ $listing == *"usr/lib/firmware/brcm/${file##*/}"* ]] || {
    cp -p "$backup" /boot/initramfs-linux-m4rch.img
    echo 'Firmware missing from the rebuilt initramfs; restored the previous image.' >&2
    exit 1
  }
done
echo 'Wi-Fi firmware installed and verified in the initramfs. Reboot to test it.'
