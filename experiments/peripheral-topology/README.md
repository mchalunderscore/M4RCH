# macOS peripheral topology

Read IORegistry without activating playback, capture or hardware controls:

```sh
ioreg -a -p IODeviceTree -l > device-tree.plist
python3 experiments/peripheral-topology/map.py device-tree.plist resources.json
```

Output retains selected DCP/display/HDMI, ISP/camera, AOP/microphone and audio
resources, immediate bus ancestry and transitive scalar phandle providers.
Property allowlisting excludes serial numbers and firmware blobs. Raw bytes are
preserved beside candidate little-endian decoding. Scalar links are resolved only
for known reference properties; clock gates and channels remain numeric data.
This is research evidence, not an automatic Linux DT conversion. Address ranges,
cell counts, clock/power namespaces, interrupts and IOMMU stream IDs still need
validation against the specific binding and driver before any hardware writes.

Use `IOService` similarly to inspect current driver bindings. A static snapshot
cannot map the active HDMI display engine conclusively: capture before/after a
direct HDMI attachment and compare HPD, EDID and provider ancestry separately
from USB-C DisplayPort. Keep raw snapshots under ignored `out/`; review reduced
output before publishing.
