# GPU register mappings

The native 25G83 GPU trial consumed the object graph and GFenderCfg, then
needed Bumper and DFenderMGPUCfg. A RAM surrogate advanced past Bumper and
exposed the next null mapping; it did not establish hardware initialization.

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

Native access, firmware mapping permissions and bank power prerequisites still
need qualification. Keep the bank scanner disabled. These are attributable
static candidates, not evidence of rendering or successful firmware startup.

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
