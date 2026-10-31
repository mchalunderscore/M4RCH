# Proton 11.0-2e ARM64: SME signal-frame fix

The installed separate compatibility tool is based on Valve Proton
`1791559733 proton-11.0-2e-arm64`. Valve's
[`proton-11.0-2e` tag](https://github.com/ValveSoftware/Proton/tree/proton-11.0-2e/wine)
pins Wine `e60892cc2398b0a83c332a2078c7b85e47bdb42b`. Its ARM64 Unix
`ntdll.so` is rebuilt with Aurora's `wine-sve-guard.patch`. All other files
came from the unmodified Valve tool. The original ntdll SHA-256 was
`9c618d49c9926f55d8a28f10c4cfd514d26e654d5bc36a1c639730abf61dd1ff`;
the installed ntdll SHA-256 is
`c086fba5b4aa080a70ea2527db2ba84cc725a0cd5828b5f9f70cabe064d6852a`.
The patch is upstream at
https://github.com/aurora-silicon/aurora-steam-native/blob/main/proton/wine-arm64-sve-payload-guard.patch.

This is a pinned, locally compiled component, not an official Valve build.
Steam does not automatically update custom tools. Do not replace its ntdll
with one from a different Wine version; rebuild and test against the exact
Wine submodule of the desired Proton release. Preserve its license.
The retained Wine patch states LGPL-2.1-or-later and attributes the target
source to André Hentschel. `COPYING.LIB` is Wine's LGPL text at the pinned
Wine revision; `COPYING` contains the accompanying GPL-2.0 text. These notices
cover the patch/source terms and do not replace the licenses included with the
Valve Proton tool or its other components.

## Reconstruction

With the exact Wine source checked out, apply the patch with `patch -p1`.
The source tree requires its generated files: run `tools/make_requests`,
`tools/make_specfiles`, and `dlls/winevulkan/make_vulkan` (using the local
`/usr/share/vulkan/registry/vk.xml` and `video.xml` and a writable
`XDG_CACHE_HOME`), followed by `autoreconf -if`. Configure in a separate build
directory with `--enable-archs=aarch64 --disable-tests --without-x`, then run
`make -j4 dlls/ntdll/ntdll.so`. The build used GCC 16.1.1 and GNU ld 2.46;
it was not built in Valve's complete Proton build environment and is not
claimed byte reproducible across toolchains. Copy the result into a separate
snapshot of the matching Valve Proton, not the Steam-managed original.

Validation so far: all 289 exported dynamic symbol names and glibc symbol
version requirements match the Valve ntdll; a 4 KiB userspace x86-64 Windows
command wrote a verified marker in a disposable prefix; the owner loaded and
played Shinri in the lobby. This is not comprehensive compatibility testing.
The historical `out/user4k-test/` logs and build configuration were removed
at the owner’s request.
