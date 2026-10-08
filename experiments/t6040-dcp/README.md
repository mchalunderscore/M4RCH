# T6040 display bring-up

The working display currently uses simpledrm; the returned native kernel config
has `DRM_APPLE` disabled. DCP owns scanout/modesetting and has a separate
firmware interface from GPU rendering. Neither working scanout nor GPU firmware
startup alone establishes accelerated presentation.

Gravity Linux at `3b85d81f656af14d0fc4bea3eef87fe040c424f9` implements DCP
26.6 support and accepts exact firmware26.6.2 for T8132. Its device match and
version checks do not yet establish T6040 support. Start with an explicit
T6040 profile and the running device tree; do not impersonate T8132.

The macOS direct-HDMI capture identifies DCPEXT0 through atc3. Native25G83
ADT translates internal DCP to `0x402e00000`, DCPEXT0 to `0x3a2e00000`, and
DCPEXT1 to `0x602e00000`. These are ASC apertures, not automatically the
Linux driver's `coproc` resource extents. Derive each resource, mailbox,
stream ID, PMGR provider and display buffer mapping individually.

Collect the native baseline without loading a driver or changing display state:

```sh
sudo python3 experiments/t6040-dcp/collect.py --output out/dcp --label baseline
```

Repeat with `--label hdmi-connected` / `hdmi-disconnected` when a direct HDMI
monitor is available. Captures include raw Linux FDT and kernel logs; treat them
as private until reviewed. Display EDIDs in the JSON are hashed, not copied.

The first trial should keep the working kernel/default, build appledrm as a
module and validate prerequisites before attempting a separate boot. In
particular, preserve the driver's `apple,bw-scratch` guard: it explicitly prevents
removing simpledrm with an incompatible tree. Confirm the exact26.6.2 IOMFB
ABI, display/PIO-DMA DART streams, firmware segments, panel and crossbar path
before takeover. Do not unload a live DCP or reset a display DART used for
scanout. A deliberately selected takeover trial can blank the screen and need
a restart; do not combine its first attempt with a GPU startup trial.

Private matching Apple binaries and boot-specific mappings live in ignored
output and the local ESP kit, not Git. Analysis has Apple binary provenance;
retain licence headers on Gravity/Asahi-derived code.
