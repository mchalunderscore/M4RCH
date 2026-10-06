# Paired scalar conversion candidate

Proposed for `drm_fb_xrgb8888_to_xrgb2101010_line`. The native sampler placed
51/64 instruction samples here; all callchains included sysfb commit work.
The patch expands two little-endian pixels per 64-bit word, preserving the
32-bit path and odd tail. No kernel SIMD, MMIO-copy, format or damage changes.
The patch modifies GPL-2.0 DRM code and retains that licensing scope.

The actual configured-kernel object compiled. Disassembly uses scalar word
loads/stores. Equivalent routines passed all 24-bit RGB values, ignored alpha,
both lanes, offsets 0–7, lengths 0–15 and sentinel checks. The scalar routine
is compiled separately with `-mgeneral-regs-only`; the timing harness uses
normal floating-point support. Run the supplied test files as separate units.

The full kernel and matching package kit now build. Extracted RAM/io-copy
wrappers passed 16,128 clipping, pitch, cache-hint, odd-width and sentinel
cases under address/undefined sanitizers. This is not a kernel KUnit or MMIO
hardware run. Native installation and matched screen-activity sampling remain.
Cached-memory loop rates are not desktop speedup evidence. Revert this single
patch for rollback; retain the accepted left-USB/capacity baseline separately.
