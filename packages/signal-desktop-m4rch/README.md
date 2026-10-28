# Signal Desktop on SME-only Apple CPUs

This local package combines the Arch Linux ARM `signal-desktop 8.32.0-1`
application and native modules with the Electron 45.0.0 runtime from the
installed `vesktop-m4rch 1.6.8-1` package. That runtime has the libyuv SME
build correction for processors that do not support non-streaming SVE. The
package copies Signal's Electron fuse settings to the replacement binary and
retains the original Signal launcher, desktop integration, and install hook.
This is a local runtime substitution, not an official Signal build.

The package and its exact build inputs are in `out/packages/` and
`out/packages/signal-desktop-m4rch-inputs/`, respectively. To rebuild this
specific version, copy both input archives and the three recipe files into an
empty build directory and run `makepkg --nodeps`. Checksums pin the two
archives and the fuse-copy helper. The recipe does not automatically track
Signal updates; updating the application or Electron requires checking ABI,
fuse layout, and startup compatibility again.

To revert to the cached signed Arch Linux ARM package, run:

```sh
sudo pacman -U /var/cache/pacman/pkg/signal-desktop-8.32.0-1-aarch64.pkg.tar.xz
```

Accept pacman's prompt to replace `signal-desktop-m4rch`. Signal database
migrations may make older application versions incompatible; this rollback
uses the same Signal application version.
