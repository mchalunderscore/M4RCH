# GPU register mappings

The native 25G83 GPU trial now programs real Bumper core masks and advances
past DFender and MCW. The next fault is a missing platform interrupt mapping.
Firmware initialization and rendering have not completed.

Static analysis of Apple's matching AGXG16X 353.14 driver supplies these
candidate mappings. The captured Linux ADT translates SGX to `0x288000000`.

| 25G83 resource / firmware slot | Bank | SGX-relative offset | Physical base | Extent |
| --- | --- | --- | --- | --- |
| 26 | GFenderCfg | `0xd04000` | `0x288d04000` | `0x8000` |
| 33 | Bumper | `0xd44000` | `0x288d44000` | `0x4000` |
| 35 | DFenderMGPUCfg | `0xe00000` | `0x288e00000` | `0x4000` |

[Evidence](evidence/2026-10-07-agx-pio-map.json) records thirteen CPU HAL
resources, source hashes, instruction addresses and limitations. The driver's
constructor adds each primary offset to the GPU physical base. The newer
26A434 host driver retains these offsets/extents but changes resource IDs.
Use the 25G83 IDs with the 25G83 firmware.

The native targeted trial confirms writes on eight exact SGX pages. Other
permissions and power prerequisites remain unqualified. Keep the bank scanner
disabled; successful individual writes do not establish complete startup.

For reproduction, decompress the matching kernelcache and extract
`com.apple.AGXG16X` using `ipsw kernel dec` and `ipsw kernel extract`, then run:

```sh
python3 tools/gpu/extract-agx-pio.py /path/to/com.apple.AGXG16X --count 13
```

Verify the count against that binary's table-length getter. The extractor reads
raw numeric records: pointer-aware dump output can incorrectly reinterpret
them as encoded addresses. It does not access hardware. Its 32-byte CPU table
records differ from the firmware's 40-byte hardware records, of which 36 bytes
are copied. Unprefixed `28`/`24` in older notes meant hexadecimal sizes.

This mapping work derives from Apple binary analysis and has non-clean-room
provenance. Raw binaries and disassembly remain in ignored local output.

The same constructor supplies platform resources outside SGX:

| Firmware slot | Resource | Physical base | Extent |
| --- | --- | --- | --- |
| 0 | GPCAICSWInt | `0x502414000` | `0x4000` |
| 9 | PushTelemetryDashboard | `0x5003d0000` | `0x4000` |
| 10 | PushTelemetryDashboardRead | `0x5003c0000` | `0x4000` |
| 11 | PushTelemetryDashboardConfigSpace | `0x5003d8000` | `0x4000` |

[Platform evidence](evidence/2026-10-07-agx-platform-map.json) records matching
constructor instructions and the native fault. Reproduce the pinned binary
check with `python3 tools/gpu/check-platform-map.py /path/to/com.apple.AGXG16X`.

Slot0+`0x634`, value`0x2000`, clears the AIC mask for IRQ429 with the native
4096-IRQ layout. It does not signal the ADT's separate software IRQ1063.
IRQ429's GPU role remains unconfirmed. The interrupt page needs an explicit
platform mapping and permission review; it is not an ordinary SGX register
page or a safe readback target. Slot11 is the following captured consumer.
These mappings are prepared for native qualification, not yet hardware-tested.
