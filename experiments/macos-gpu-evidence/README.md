# macOS Metal reference evidence helpers

These helpers produced the private 19 October 2026 macOS reference captures.
The Metal target is 64x64 RGBA8, three vertices, one sample, constant orange on
opaque black, with no depth/MSAA/compute. A completed blit provides readback;
barycentric CPU checks and an independent PNG decoder verify the image. The
bounded workload runs while full IOService/IODeviceTree snapshots are captured.
CoreGraphics enumerates display modes without changing them. An optional Metal
capture uses the supported capture API; full Xcode is not required when the
runtime supports gpuTraceDocument. Instruments is probed separately.

Copy source/ to a fresh ignored output directory before collecting. Do not run
in an existing capture directory; phases are created exclusively. On this Mac:

```sh
mkdir -p out/macos-reference-new/source
cp experiments/macos-gpu-evidence/source/* out/macos-reference-new/source/
cd out/macos-reference-new
xcrun swiftc -O source/triangle.swift -o triangle -framework Metal -framework CoreGraphics -framework ImageIO
xcrun swiftc -O source/display-modes.swift -o display-modes -framework CoreGraphics
python3 source/collect.py
python3 source/verify-png.py
python3 source/summarize-registry.py
```

The collector expects the existing M4RCHESP mounted at /Volumes/M4RCHESP so it
can verify boot.bin, GRUB and EFI executable hashes before/after. It reads system
information and writes captures locally. It starts/stops only its Metal process;
no reboot, sleep, display-mode change, raw MMIO, firmware memory access, driver
reset or boot/security-setting change is performed. Its process has a 240-second
maximum. Normal background applications remain running; baseline is not a claim
of GPU power-off. Raw registries, traces, PNG/RGBA output and binaries stay local
or in the private ESP package rather than in Git.

The 26A434 capture reported AGX 360.34.5 / GFX RTKit 3514.0.15, whereas the older
Linux private reference is 25G83 / AGX 353.14 / RTKit 3255.160.4. Confirm the
Linux-loaded firmware before comparing private layouts. Metal success and client
detachment do not establish Linux rendering, physical OFF or DMA retirement.

ESP package: MACOSEV/20261019T1330/macos-gpu-evidence-20261019T1330.tar.gz.
SHA256: 9c6ea8faa75742ce8f02dcba435cab80963a213fd4f321913e9d28b0fa6cc0c2.
Read RETURN.md and SUPPLEMENT.md beside it before comparing with Linux.
