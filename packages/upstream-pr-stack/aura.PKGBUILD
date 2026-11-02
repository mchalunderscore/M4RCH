pkgname=aura
pkgver=1.0.0b1.r20261101
pkgrel=2.2
pkgdesc='Aurora stage-two loader built from the tested upstream PR stack'
arch=('aarch64')
url='https://github.com/aurora-silicon/aura'
license=('MIT' 'GPL-2.0-only')
depends=('asahi-scripts>=20260127.1' 'uboot-aurora')
provides=('m1n1=1.6.1.aurora19' 'm1n1-aurora=1.6.1.aurora19' 'm1n1-neo=1.6.1.aurora19')
conflicts=('m1n1' 'm1n1-aurora' 'm1n1-neo')
replaces=('m1n1-neo')
options=('!strip' '!debug')
source=()
package() {
  local base=/home/michal/Projects/m4rch/cache
  bsdtar -xf "$base/aura-j614s-staged/aura-1.0.0b1.r20261101-2.1-aarch64.pkg.tar.xz" -C "$pkgdir" usr
  install -m644 "$base/upstream-stack/aura/build/aura.bin" "$pkgdir/usr/lib/asahi-boot/m1n1.bin"
  printf '%s\n' 'Tested PR stack: Aura source merge 3bb98101f66964c7f479d01171d6d7aaa129fc6d; the stage1 files are preserved from the previous package and were not enrolled.' > "$pkgdir/usr/share/doc/aura/M4RCH-PROVENANCE"
  printf '%s\n' '{"stage2_source_commit":"3bb98101f66964c7f479d01171d6d7aaa129fc6d","stage2_boot_tested":true,"stage1_source_commit":"a9cad94edb46fd4baf77c6cb1776b3bb5f1a566f","stage1_auto_enrollment":false}' > "$pkgdir/usr/share/doc/aura/build-qualification.json"
}
