pkgname=linux-aurora
pkgver=7.3.0.aurora1
pkgrel=9.5
pkgdesc='Aurora kernel built from the tested J614s upstream PR stack'
arch=('aarch64')
url='https://github.com/aurora-silicon/linux'
license=('GPL2')
depends=('coreutils' 'kmod' 'initramfs' 'aura>=0.1.0.r20261029')
provides=(WIREGUARD-MODULE "linux-asahi=$pkgver")
conflicts=('linux-asahi')
options=('!strip' '!debug')
source=()
package() {
  local base=/home/michal/Projects/m4rch/cache/upstream-stack
  local ver=7.3.0-j614s-pr1-ARCH
  local dst="$pkgdir/usr/lib/modules/$ver"
  mkdir -p "$dst"
  cp -a "$base/trial/root/usr/lib/modules/$ver/." "$dst/"
  install -m644 "$base/trial/Image" "$dst/vmlinuz"
  install -m644 "$base/kernel-build/.config" "$dst/config"
  printf '%s\n' linux-aurora > "$dst/pkgbase"
  install -d "$dst/dtbs"
  install -m644 "$base"/kernel-build/arch/arm64/boot/dts/apple/*.dtb "$dst/dtbs/"
  install -d "$pkgdir/usr/share/doc/linux-aurora"
  printf '%s\n' 'Tested PR stack: linux merge c6af520e2920e3b5b2b604b23e89b2fcede369e3; #795 dc054fb02bfb002e41f2dd8f43a3dce2983cf537; #821 4ca62110a994f246c5c97806ab70974b1f0e7e32; #804 c6665bed9ad1dce905ee35c4cebaf44054792ebb; #817 f015a5c51644cea20421f7ae571fe03dd24705e9.' > "$pkgdir/usr/share/doc/linux-aurora/M4RCH-PROVENANCE"
}
