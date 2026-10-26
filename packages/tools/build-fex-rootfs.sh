#!/bin/bash
# Run as root in a disposable Debian 13 amd64 build VM. Building through
# Rosetta requires /proc to be bind-mounted in the debootstrap chroot.
# Mesa sources must be the same pinned source used by mesa-m4rch.
set -euo pipefail
work=${1:-/work}
out=${2:-/project/out/packages/source}
root=$work/rootfs
mkdir -p "$out"
if [[ ! -f $root/etc/debian_version ]]; then
    mkdir -p "$root/proc"
    mount --bind /proc "$root/proc"
    debootstrap --foreign --variant=minbase --arch=amd64 trixie "$root" http://deb.debian.org/debian
    mountpoint -q "$root/proc" || mount --bind /proc "$root/proc"
    DEBOOTSTRAP_DIR="$root/debootstrap" debootstrap --second-stage --second-stage-target="$root"
fi
mountpoint -q "$root/proc" || mount --bind /proc "$root/proc"
cp /etc/resolv.conf "$root/etc/resolv.conf"
cat >"$root/etc/apt/sources.list" <<'EOF'
deb http://deb.debian.org/debian trixie main
deb http://deb.debian.org/debian trixie-updates main
deb http://deb.debian.org/debian-security trixie-security main
EOF
printf '#!/bin/sh\nexit 101\n' >"$root/usr/sbin/policy-rc.d"
chmod 755 "$root/usr/sbin/policy-rc.d"
chroot "$root" dpkg --add-architecture i386
chroot "$root" apt-get update
# Debian's ordinary Steam dependency packages plus the common graphics,
# audio and UI libraries needed by Steam's own runtime on both architectures.
libs=(libegl1 libgbm1 libvulkan1 libasound2t64 libasound2-plugins libpulse0
      libdbus-1-3 libnss3 libfontconfig1 libfreetype6 libsdl2-2.0-0 libxi6
      libxrandr2 libxrender1 libxcursor1 libxfixes3 libxss1 libxtst6 libxcomposite1
      libxcb-keysyms1 libx11-xcb1 libwayland-client0 libwayland-server0
      libxcb-dri3-0 libxcb-present0 libxcb-randr0 libxcb-shm0 libxcb-sync1
      libxcb-xfixes0 libxshmfence1 libexpat1 libzstd1 libudev1)
packages=(steam-libs:amd64 steam-libs-i386:i386 bash ca-certificates curl file
          xz-utils python3 xdg-utils zenity dbus-bin fonts-liberation)
for lib in "${libs[@]}"; do packages+=("$lib:amd64" "$lib:i386"); done
chroot "$root" /usr/bin/env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "${packages[@]}"
# Install build-fex-mesa.sh's paired Mesa into Debian's multiarch paths.
# No compiler, build tree or host libraries go into the image.
test -s "$work/mesa-runtime/usr/lib/x86_64-linux-gnu/libvulkan_asahi.so"
test -s "$work/mesa-runtime/usr/lib/i386-linux-gnu/libvulkan_asahi.so"
test -s "$work/mesa-runtime/usr/lib/x86_64-linux-gnu/libVkLayer_MESA_device_select.so"
test -s "$work/mesa-runtime/usr/lib/i386-linux-gnu/libVkLayer_MESA_device_select.so"
cp -a "$work/mesa-runtime/." "$root/"
chroot "$root" ldconfig
chroot "$root" dpkg-query -W -f='${binary:Package}\t${Version}\n' >"$out/debian-packages.txt"
chroot "$root" apt-get clean
rm -f "$root/usr/sbin/policy-rc.d" "$root/etc/machine-id"
rm -rf "$root/var/lib/apt/lists"/* "$root/var/log"/* "$root/tmp"/*
# FEX resolves files from the image first and falls back to the host. Leave
# DNS and user identity to the running host, rather than shadowing them with
# the build VM's files (or an empty resolv.conf).
rm -f "$root"/etc/{resolv.conf,hosts,hostname,passwd,passwd-,group,group-,shadow,shadow-,gshadow,gshadow-,machine-id,mtab,fstab,subuid,subgid,timezone,localtime}
rm -f "$root/var/lib/dbus/machine-id"
umount "$root/proc"
# Match upstream FEX's runtime-directory cleanup: these must resolve to the
# running host rather than empty or static read-only directories in the image.
rm -rf "$root"/{boot,home,media,mnt,root,srv,tmp,run,proc,sys,dev}
rm -rf "$root"/var/{tmp,run,lock}
printf '%s\n' 'Debian 13 (trixie), amd64 + i386' \
    'Mesa: aurora-silicon/mesa f2c9dc3fb59c81fdaf51f19884175c856e3d1889' \
    'Graphics: asahi Vulkan/native-context and Zink OpenGL, both architectures' \
    'Debian package licenses: /usr/share/doc/*/copyright inside the image' \
    >"$out/debian-build-info.txt"
mkfs.erofs -zlz4hc -T 1792972800 "$out/debian.erofs" "$root"
fsck.erofs "$out/debian.erofs"
