#!/bin/bash
# Integration checks run only in the disposable Arch build VM.
set -euo pipefail
out=/project/out/packages
shopt -s nullglob
packages=("$out"/*.pkg.tar.zst "$out"/dependencies/*.pkg.tar.xz "$out"/dependencies/*.pkg.tar.zst)

# Check the real target's dependency database, including removal of its old
# all-in-one configuration package. This root is disposable and runs no hooks.
root=/work/package-dependency-check
rm -rf "$root"
mkdir -p "$root/var/lib/pacman" "$root/etc/pacman.d/hooks"
cp -a "$out/native-pacman-local" "$root/var/lib/pacman/local"
cat >/work/package-check.conf <<'CONF'
[options]
Architecture = aarch64
SigLevel = Required DatabaseOptional
LocalFileSigLevel = Optional
CONF
obsolete=()
for name in linux-m4rch-gpu-contract linux-m4rch-gpu-id linux-m4rch-gpu-port; do
    if pacman --root "$root" -Q "$name" >/dev/null 2>&1; then obsolete+=("$name"); fi
done
if ((${#obsolete[@]})); then
    pacman --root "$root" --config /work/package-check.conf -R --noconfirm "${obsolete[@]}"
fi
ln -s /dev/null "$root/etc/pacman.d/hooks/95-m1n1-install.hook"
pacman --root "$root" --config /work/package-check.conf --gpgdir /etc/pacman.d/gnupg -U --noconfirm --ask=4 --noscriptlet "${packages[@]}"
for name in linux-m4rch mesa-m4rch m1n1-m4rch u-boot-m4rch linux-firmware-vendor-m4rch alsa-ucm-conf-m4rch asahi-scripts-m4rch mesa-flatpak-m4rch muvm-m4rch fex-emu-m4rch avd-fw-m4rch fex-rootfs-debian-m4rch steam-m4rch mbpfan-m4rch vesktop-m4rch; do
    pacman --root "$root" -Qk "$name"
done
echo 'PASS: target package dependencies and ownership'

# Exercise the actual distribution hooks in a complete Arch system. The old
# validation disabled mkinitcpio in this VM; remove that test-only mask.
rm -f /etc/pacman.d/hooks/90-mkinitcpio-install.hook
mkdir -p /boot/grub
cp "$out/source/previous-boot.bin" /boot/boot.bin
pacman -U --noconfirm --ask=4 "${packages[@]}"
test -s /boot/vmlinuz-linux-m4rch
test -s /boot/initramfs-linux-m4rch.img
cmp /boot/vmlinuz-linux-m4rch /usr/lib/modules/7.3.0-m4rch/vmlinuz
grep -aq 'Linux version 7.3.0-m4rch ' /boot/vmlinuz-linux-m4rch
grep -q '^CONFIG_KVM=y$' /usr/share/doc/linux-m4rch/config
test -s /usr/lib/firmware/apple/aop-als-cal.bin
test -s /usr/lib/firmware/apple/avd-fw-v5-t1.bin
lsinitcpio /boot/initramfs-linux-m4rch.img >"$out/initramfs-files.txt"
grep -q 'apple-silicon.conf' "$out/initramfs-files.txt"
! grep -Eq 'm4rch-root|m4rch-drivers|aurora-direct|aurora-userspace' "$out/initramfs-files.txt"
test -s /boot/boot.bin.old
test "$(stat -c %s /boot/boot.bin)" -lt "$((4587520 - 32768))"
test "$(fdtget /usr/lib/asahi-boot/apple-j614s.dtb / model)" = 'Apple MacBook Pro (14-inch, M4 Pro)'
! find /usr/lib/modules/7.3.0-m4rch -name '*tas2764.ko*' -o -name '*tas2770.ko*' | grep -q .
# Check all requested drivers exist without inserting them into the VM kernel.
modules=$(sed -n 's/^ExecStart=\/usr\/bin\/modprobe -a //p' /usr/lib/systemd/system/apple-silicon.service)
for module in $modules; do
    modprobe --set-version 7.3.0-m4rch --show-depends "$module" >/dev/null
done
systemd-analyze verify /usr/lib/systemd/system/apple-silicon.service
grub-mkconfig -o /boot/grub/grub.cfg
grub-script-check /boot/grub/grub.cfg
grep -q 'vmlinuz-linux-m4rch' /boot/grub/grub.cfg
grep -q 'initramfs-linux-m4rch.img' /boot/grub/grub.cfg
# This kernel enables the J614s display nodes only with this early parameter.
grep -Eq 'linux[[:space:]]+/boot/vmlinuz-linux-m4rch .*m4rch.dcp=1' /boot/grub/grub.cfg
grep -qx 'terminal_output console' /boot/grub/grub.cfg
! grep -Eq 'm4rch.packaged=|aurora_gpu' /boot/grub/grub.cfg

# A subsequent ordinary kernel transaction must refresh the same boot files.
pacman -U --noconfirm "$out"/linux-m4rch-*.pkg.tar.zst
cmp /boot/vmlinuz-linux-m4rch /usr/lib/modules/7.3.0-m4rch/vmlinuz
for file in /usr/lib/libvulkan_asahi.so /usr/lib/libEGL_mesa.so.0 /usr/lib/libGLX_mesa.so.0 /usr/lib/libgbm.so.1; do
    ! ldd "$file" | grep -q 'not found'
    ! readelf -d "$file" | grep -E '(RPATH|RUNPATH).*aurora-direct'
done
echo 'PASS: stock depmod/mkinitcpio hooks, upstream update-m1n1, stock GRUB generation, kernel reinstall, driver availability, speaker exclusion, Mesa dependencies'
