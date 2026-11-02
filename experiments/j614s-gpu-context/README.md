# J614s GPU context observation

This experiment investigates the unqualified 16-core GPU buffer layout in [Linux #804](https://github.com/aurora-silicon/linux/pull/804). The test patch and workload are retained for future investigation. The trial kernel and GRUB entry have been retired; a future run requires a newly prepared and verified instrumented kernel and a recovery plan.

The PID-gated kernel patch summarizes compute preemption and operand-state buffers at queue-idle boundaries without intentionally printing their contents or GPU addresses. The workload uses competing compute queues, CPU-checked output and an in-dispatch marker. Host observation of the marker is a platform-specific diagnostic, not a Vulkan guarantee. Neither buffer changes nor overlapping GPU intervals alone establish a context save or restore; the tests do not qualify render deflake or every offset.

On the J614s trial, the workload completed and checked output passed, but the buffers also changed during solo calibration before the competing queue was submitted. The trace did not identify a save/restore event. The result is **inconclusive** for preemption and the layout.

The original trial source archive and local source delta, kernel configurations, compressed symbol-bearing kernel, workload, private results and Apple-derived reference binaries are under `/home/michal/.local/share/m4rch-archive/cleanup-20261102/cache/gpu-context-trial/`. Keep Apple binaries and raw firmware data private. The retired trial kernel, initramfs, modules and GRUB entry are archived under `/var/lib/m4rch/gpuobs-retired-20261102/trial.tar.zst`. This is not the normal boot recovery archive; use [recovery](../../docs/recovery.md) for that.

For a new trial, verify the build and boot configuration first. Set `M4_GPU_TRIAL_DIR` to a prepared private directory containing `gpu-live-marker` and `live-marker.spv`; the runner refuses a kernel release other than `7.3.0-1-14-gpuobs` and records results there. Its marker, queue intervals and buffer fingerprints require an independently observable interruption and a discriminating control before they can support a preemption claim.
