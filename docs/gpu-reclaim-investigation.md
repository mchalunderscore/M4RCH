# GPU memory and reclaim

The installed Aurora-derived driver uses shared system RAM for GPU objects.
Its GPU allocation ledger and process/cgroup memory figures overlap; do not
add them as separate totals. During an earlier Steam workload, pressure and
GPU residency rose substantially. Diagnostic observations did not establish
a single cause or prove how much memory a future workload will reclaim.

The owner subsequently reported Steam and Shinri stability and responsiveness
to be about as good as macOS. This is practical testing, not a guarantee for
every workload. See [Steam and graphics](steam-acceleration.md) and
[Plasma memory](plasma-memory-investigation.md) for the current notes. The
detailed trial history remains in Git at `e7baa0e`.
