# Matching build files, following Aurora's linux-aurora-headers packaging.
pkgname=linux-aurora-headers
pkgver=7.3.0.aurora1
pkgrel=9.6
pkgdesc='Headers for the merged J614s Aurora kernel candidate'
arch=('aarch64')
url='https://github.com/aurora-silicon/linux'
license=('GPL2')
depends=('pahole')
provides=("linux-asahi-headers=$pkgver")
conflicts=('linux-asahi-headers')
options=('!strip' '!debug')
source=()

package() {
  local base=/home/michal/Projects/m4rch/cache/upstream-stack
  local src="$base/linux-merged795" out="$base/kernel-build-merged795"
  local ver=7.3.0-j614s-merged795-ARCH+ builddir="$pkgdir/usr/lib/modules/7.3.0-j614s-merged795-ARCH+/build"
  [[ $(git -C "$src" rev-parse HEAD) == 9fa275dd0435aa07a4a2ec507201d4fd3bde8b14 ]]
  [[ -z $(git -C "$src" status --porcelain) ]]
  [[ $(<"$out/include/config/kernel.release") == "$ver" ]]
  cd "$src"
  install -Dt "$builddir" -m644 "$out/.config" Makefile "$out/Module.symvers" "$out/System.map" "$out/vmlinux"
  printf '%s\n' "$ver" > "$builddir/version"
  install -Dt "$builddir/kernel" -m644 kernel/Makefile
  cp -t "$builddir" -a scripts "$out/scripts"
  install -Dt "$builddir/tools/bpf/resolve_btfids" "$out/tools/bpf/resolve_btfids/resolve_btfids"
  cp -t "$builddir" -a include "$out/include"
  install -Dt "$builddir/arch/arm64" -m644 arch/arm64/Makefile
  install -Dt "$builddir/arch/arm64/kernel" -m644 "$out/arch/arm64/kernel/asm-offsets.s"
  cp -t "$builddir/arch/arm64" -a arch/arm64/include "$out/arch/arm64/include"
  install -Dt "$builddir/drivers/md" -m644 drivers/md/*.h
  install -Dt "$builddir/net/mac80211" -m644 net/mac80211/*.h
  install -Dt "$builddir/drivers/media/i2c" -m644 drivers/media/i2c/msp3400-driver.h
  install -Dt "$builddir/drivers/media/usb/dvb-usb" -m644 drivers/media/usb/dvb-usb/*.h
  install -Dt "$builddir/drivers/media/dvb-frontends" -m644 drivers/media/dvb-frontends/*.h
  install -Dt "$builddir/drivers/media/tuners" -m644 drivers/media/tuners/*.h
  install -Dt "$builddir/drivers/iio/common/hid-sensors" -m644 drivers/iio/common/hid-sensors/*.h
  find . -path './.git' -prune -o -name 'Kconfig*' -type f -exec install -Dm644 '{}' "$builddir/{}" \;
  find -L "$builddir" -type l -delete
  find "$builddir" -type f \( -name '*.o' -o -name '*.cmd' \) -delete
  install -d "$pkgdir/usr/src"
  ln -sr "$builddir" "$pkgdir/usr/src/linux-aurora"
}
