pkgname=uboot-aurora
pkgver=2026.07.aurora6
pkgrel=1.2
pkgdesc='Aurora U-Boot built from the tested J614s upstream PR'
arch=('aarch64')
url='https://github.com/aurora-silicon/u-boot'
license=('GPL-2.0-or-later')
provides=("uboot-asahi=$pkgver")
conflicts=('uboot-asahi' 'uboot-asahi-j700')
replaces=('uboot-asahi-j700')
options=('!strip' '!debug')
source=()
package() {
  local base=/home/michal/Projects/m4rch/cache
  bsdtar -xf "$base/uboot-aurora-20261101/uboot-aurora-2026.07.aurora6-1.1-aarch64.pkg.tar.xz" -C "$pkgdir" usr
  install -m644 "$base/upstream-stack/uboot-build/u-boot-nodtb.bin" "$pkgdir/usr/lib/asahi-boot/u-boot-nodtb.bin"
  install -d "$pkgdir/usr/share/doc/uboot-aurora"
  printf '%s\n' 'Tested upstream PR #29 source 7a6dc91397981d52339be0fa7cce981bc5d47c2d.' > "$pkgdir/usr/share/doc/uboot-aurora/M4RCH-PROVENANCE"
}
