# Package the locally built Aurora #795 merge plus the remaining upstream PRs.
pkgname=linux-aurora
pkgver=7.3.0.aurora1
pkgrel=9.6
pkgdesc='Aurora kernel built from the merged J614s tree and remaining upstream PRs'
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
  local ver=7.3.0-j614s-merged795-ARCH+
  local dst="$pkgdir/usr/lib/modules/$ver"
  [[ $(git -C "$base/linux-merged795" rev-parse HEAD) == 9fa275dd0435aa07a4a2ec507201d4fd3bde8b14 ]]
  [[ -z $(git -C "$base/linux-merged795" status --porcelain) ]]
  [[ $(<"$base/kernel-build-merged795/include/config/kernel.release") == "$ver" ]]
  [[ -s "$base/kernel-build-merged795/arch/arm64/boot/Image" ]]
  [[ -s "$base/merged795-package/root/usr/lib/modules/$ver/modules.dep" ]]
  mkdir -p "$dst"
  cp -a "$base/merged795-package/root/usr/lib/modules/$ver/." "$dst/"
  install -m644 "$base/kernel-build-merged795/arch/arm64/boot/Image" "$dst/vmlinuz"
  install -m644 "$base/kernel-build-merged795/.config" "$dst/config"
  printf '%s\n' linux-aurora > "$dst/pkgbase"
  install -d "$dst/dtbs"
  install -m644 "$base"/kernel-build-merged795/arch/arm64/boot/dts/apple/*.dtb "$dst/dtbs/"
  install -d "$pkgdir/usr/share/doc/linux-aurora"
  printf '%s\n' 'Aurora Linux #795 merge dc87ceeea59f7b1075fd5e7659869dc12dd16ca9; #821 4ca62110a994f246c5c97806ab70974b1f0e7e32; #804 c6665bed9ad1dce905ee35c4cebaf44054792ebb; #817 f015a5c51644cea20421f7ae571fe03dd24705e9. Unbooted candidate.' > "$pkgdir/usr/share/doc/linux-aurora/M4RCH-PROVENANCE"
}
