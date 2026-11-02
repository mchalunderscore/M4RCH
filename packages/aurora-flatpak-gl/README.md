# Flatpak graphics extension

The Aurora extension is staged with the same Zink drawable lifetime fix as
native Mesa. The previous Flatpak-only workaround for llvmpipe's LLVM shader
cache has been retired. Without an LLVM build ID or a usable timestamp, Mesa
may disable the software renderer's disk shader cache; GPU-accelerated Zink is
not affected by that cache setting.

The original workaround, review experiment, test logs and package remain in
`cache/flatpak-llvm-cache-20261101/`. A proof LLVM build with build IDs
produced distinct IDs and restored cache hits, but the full Flathub SDK build
and export pipeline were not tested. The unsubmitted proposal is no longer
carried in the active tree.
