#!/bin/bash
# Install the prepared packages using ordinary Arch tools. Never reboots.
set -Eeuo pipefail
shopt -s nullglob
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
(( EUID == 0 )) || { echo "Run: sudo bash $here/install.sh" >&2; exit 1; }
[[ $(findmnt -n -o FSTYPE --mountpoint /boot) == vfat ]] || {
    echo 'Mount the ESP at /boot first.' >&2; exit 1;
}
(cd "$here"; sha256sum -c SHA256SUMS)
names=(linux-m4rch mesa-m4rch m1n1-m4rch u-boot-m4rch
       linux-firmware-vendor-m4rch alsa-ucm-conf-m4rch asahi-scripts-m4rch
       mesa-flatpak-m4rch muvm-m4rch fex-emu-m4rch avd-fw-m4rch
       fex-rootfs-debian-m4rch steam-m4rch mbpfan-m4rch vesktop-m4rch)
packages=()
for name in "${names[@]}"; do
    matches=("$here/$name"-*.pkg.tar.zst)
    ((${#matches[@]} == 1)) || { echo "Expected one archive for $name" >&2; exit 1; }
    packages+=("${matches[0]}")
done
packages+=("$here"/dependencies/*.pkg.tar.zst "$here"/dependencies/*.pkg.tar.xz)
backup=/root/boot-backup-$(date +%Y%m%d-%H%M%S)
mkdir -p "$backup"
cp -a /boot/boot.bin /boot/grub/grub.cfg "$backup/"
# The existing 'Previous working system' GRUB entry is retained by grub-mkconfig.
pacman -U --noconfirm --ask=4 "${packages[@]}"
systemctl enable mbpfan.service
# GL.host supplies the paired Mesa inside Flatpak, using Flatpak's own extension
# mechanism. Apply the same renderer selection used by the host desktop.
flatpak override --system --env=LIBGL_ALWAYS_SOFTWARE=0 \
    --env=MESA_LOADER_DRIVER_OVERRIDE=zink --env=GALLIUM_DRIVER=zink
mkinitcpio -P
update-m1n1
grub-mkconfig -o /boot/grub/grub.cfg
printf '\nInstalled. Arch Linux is the default GRUB entry. Reboot when ready.\n'
