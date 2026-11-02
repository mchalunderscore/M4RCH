# zink: retire cached Wayland targets when drawables are released

When a Wayland surface is destroyed and a later surface reuses its client
pointer, Zink can find the old display target in its cache. Presenting then
uses a synchronization object associated with the destroyed surface, and the
compositor disconnects the client with `wp_linux_drm_syncobj_surface_v1: The
surface has been destroyed`.

Track live Wayland drawables per surface and detach the cached target when
the last drawable is released. Keep outstanding target resources referenced,
avoid removing a replacement target at the same address, and protect cache
lookup and final reference removal with the existing lock. Related: #137,
which includes the standalone reproducer and a full report.

On a J614s M4 Pro with Umbriel, the unpatched Aurora Mesa source failed five
of five standalone Wayland/EGL runs after surface-address reuse. This change
passed five runs of 15 iterations each, with 13 address reuses per run. It
also passed five runs where multiple drawables share one Wayland surface and
one drawable is recreated while another remains alive. An eviction-on-every-
destroy variant failed the shared-surface test with a duplicate syncobj error.

The affected files at the target `aurora-wip` base are byte-identical to the
hardware-tested Mesa revision. Full graphics CTS and dedicated multithreaded
stress testing have not been run; review of cache lifetime and synchronization
is requested before this is considered ready to merge.
