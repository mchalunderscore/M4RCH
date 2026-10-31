# Signal Desktop on SME-only Apple CPUs

This local package combines the Arch Linux ARM `signal-desktop 8.32.0-1`
application and native modules with the Electron 45.0.0 runtime from the
installed `vesktop-m4rch 1.6.8-1` package. That runtime has the libyuv SME
build correction for processors that do not support non-streaming SVE. The
package copies Signal's Electron fuse settings to the replacement binary and
retains the original Signal launcher, desktop integration, and install hook.
This is a local runtime substitution, not an official Signal build.

The signed original Signal package and the Vesktop binary package are cached
under `/var/cache/pacman/pkg/` and `/var/cache/pacman/pkg/m4rch/`, respectively.
The recipe verifies both package archives and the fuse-copy helper. It extracts
the Electron runtime from the cached Vesktop package; this repackages binaries
and does not rebuild Electron or Vesktop from source. To build as a normal user:

```sh
workdir=$(mktemp -d)
cp packages/signal-desktop-m4rch/{PKGBUILD,copy-fuses.py,signal.install} "$workdir/"
cp /var/cache/pacman/pkg/signal-desktop-8.32.0-1-aarch64.pkg.tar.xz "$workdir/signal-original.pkg.tar.xz"
cp /var/cache/pacman/pkg/m4rch/vesktop-m4rch-1.6.8-1-aarch64.pkg.tar.zst "$workdir/vesktop-runtime.pkg.tar.zst"
(cd "$workdir" && makepkg)
```

Run these commands from the repository root. The build does not install the
result. The cached Vesktop package is a local build; its hash verifies the
chosen input, not its upstream source provenance.

Aurora's current [package collection](https://github.com/aurora-silicon/alarm-aurora/tree/main/packages)
does not provide this runtime substitution. Signal's Linux ARM64 CI proposal
[#7202](https://github.com/signalapp/Signal-Desktop/pull/7202) was closed
unmerged, as was its [Debian ARM64 build proposal](https://github.com/signalapp/Signal-Desktop/pull/7965);
the latter records plans for official ARM64 packages. Neither supplies this
installed local combination.

The recipe does not automatically track Signal updates; updating the
application or Electron requires checking ABI, fuse layout, and startup
compatibility again.

To revert to the cached signed Arch Linux ARM package, run:

```sh
sudo pacman -U /var/cache/pacman/pkg/signal-desktop-8.32.0-1-aarch64.pkg.tar.xz
```

Accept pacman's prompt to replace `signal-desktop-m4rch`. Signal database
migrations may make older application versions incompatible; this rollback
uses the same Signal application version.
