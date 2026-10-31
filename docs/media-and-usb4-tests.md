# J614s media and USB4 qualification

Snapshot: 31 October 2026, boot `c7c08627-2c0d-4806-bf4b-3933df129d1b`,
`linux-m4rch 7.3.0-28`, `mesa-m4rch 1:26.3.0.r20261031.c208afc-1`.
These observations are capability checks, not successful workload tests.

## Hardware video decoding

The `apple_avd` driver initialized hardware version `40010`. The `avd` node
`/dev/video0` enumerates stateless H.264, VP9 and AV1 input; HEVC is not
advertised. The installed [VA-API bridge](../packages/libva-v4l2-request-m4rch/README.md)
completed bit-exact H.264 and VP9 frame comparisons against software, including 5,400 H.264 frames from a three-minute 720p stream. The package-managed system-wide session environment selects the bridge by default. The
short clips, logs and frame hashes are in `cache/media-qualification/`.

The direct GStreamer H.264 test is `experiments/media-qualification/check-h264.sh`.
It converts the decoder's padded NV12 buffers to planar I420 before comparing
all 90 frames. Plugins used for the trial were extracted from signature-checked
Arch Linux ARM packages into the cache, not installed system-wide. Test with:

```sh
export LD_LIBRARY_PATH="$PWD/cache/media-qualification/gst-root/usr/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export GST_PLUGIN_PATH="$PWD/cache/media-qualification/gst-root/usr/lib/gstreamer-1.0"
export GST_REGISTRY="$PWD/cache/media-qualification/gst-registry.bin"
bash experiments/media-qualification/check-h264.sh
```

These short streams do not qualify arbitrary videos, 10-bit decode, display
output, browsers, suspend or AV1; upstream has reported AV1 faults on M3 Pro.

Asahi's [M4 support table](https://asahilinux.org/docs/platform/feature-support/m4/)
marks the decoder WIP. The [AVD userspace fork](https://github.com/omacom/libva-v4l2_request)
documents V4L2 Request translation and limitations; its published test evidence
is for M1, not this M4 Pro. It is a lead, not proof of J614s support.

## Ray tracing

On the running Vulkan stack, `vulkaninfo` identifies the physical GPU as
`Apple M4 Pro (G16S B1)`, driver Borealis. It advertises
`VK_KHR_acceleration_structure` and its feature, but neither
`VK_KHR_ray_query` nor `VK_KHR_ray_tracing_pipeline`. The separate CPU device
llvmpipe advertises both, so its extensions must not be attributed to the
Apple GPU. A small upstream `rt.asbuild` benchmark completed on the M4 Pro after a local harness change allowing acceleration structures without ray query; it built 960 triangles. This is not a ray-tracing workload. Vulkan ray query and ray-tracing
pipeline are separate APIs; an acceleration-structure capability alone does
not prove either path works or whether dedicated hardware is used. See the
[Khronos Vulkan ray-tracing guide](https://github.com/KhronosGroup/Vulkan-Guide/blob/main/chapters/extensions/ray_tracing.adoc).

After an appropriate GPU driver update, repeat `vulkaninfo` and inspect the
Apple GPU's own extension and feature section. If either ray API is exposed,
run a small sample explicitly selecting that GPU and compare its rendered
output with a reference. Record device, driver, enabled extension, result and
logs; distinguish GPU execution from llvmpipe and from dedicated RT hardware.
The present stack does not expose the extensions required for that sample.
The [kernel M4 Pro integration](https://github.com/aurora-silicon/linux/pull/408)
and [Mesa M4 support](https://github.com/aurora-silicon/mesa/pull/55) explicitly
leave traversal disabled on 25G83; the kernel source warns that stalled
traversal wedges the GPU without firmware recovery. The later [Mesa split](https://github.com/aurora-silicon/mesa/pull/80)
likewise requires a validated G16S traversal and recovery contract. Merely
flipping the feature bit is not a fix.

The AS-only harness patch is `experiments/media-qualification/gpubench-as-only.patch`,
against Aurora gpubench `0dae261cb8de9cade5825425777a257ff224482f` (source
archive SHA-256 `150aac13a62e27e2c3e82eff98f65bac797e3e0448e261eb3a0650f060b7b5ea`).
It enables only the advertised acceleration-structure API and preserves the
ray-query gate. A single build completed; it does not check traversal or prove
acceleration-structure content correctness.

## Thunderbolt / USB4

The running system has no entries in `/sys/bus/thunderbolt/devices`; the
Thunderbolt module is loaded. This does not establish whether the controller
can enumerate a device. USB 3 devices, ordinary USB-C hubs and DP Alt Mode
monitors do not independently prove Thunderbolt or USB4 tunneling.

A suitable test device is a known Thunderbolt 3/4 or USB4 NVMe enclosure,
dock with a PCIe device, or another Thunderbolt/USB4 computer, together with
a cable rated for that connection. A USB-only enclosure or charging cable is
not sufficient. Before and after connecting, capture `lspci -nnk`,
`lsusb -t`, `find /sys/bus/thunderbolt/devices -maxdepth 1 -mindepth 1 -printf '%f\n'`,
and `journalctl -k -b` for USB4/Thunderbolt messages. A new Thunderbolt domain
and device plus an identifiable PCIe endpoint would be stronger evidence than
USB devices appearing; then test a non-destructive read from known storage.
Do not change authorization or write to the device until its identity and
mounts are known. If nothing appears, compare on another machine and cable
before attributing the result to the Mac. Linux's [USB4 and Thunderbolt guide](https://docs.kernel.org/7.2/admin-guide/thunderbolt.html)
describes device discovery and authorization.
