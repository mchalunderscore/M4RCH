# Common G16 work encoder: dependencies through publication

Matched private AGX353.14 binary, numeric evidence only. The body audit checks
1,024 cases; a separate composite audit checks another 1,024 cases spanning the
previously qualified prefix and this body together. Both execute the actual
uncached timestamp helper and actual LDADDAL publication instruction. Full
0x200-byte output and 0x100-byte queue comparisons match independent models.
This is single-thread RAM emulation, not live firmware acceptance.

## Explicit and implicit dependencies

Input begins with u32 dependency count, followed immediately by 12-byte entries.
Each entry supplies u32 timestamp at0 and signed event index at4. Word8 is not
read here. Event index selects a 24-byte epoch record through the event machine
and also supplies low7 bits ORed at bit40 in the packed dependency. Converted
timestamp and original bits47..63 form the rest of that word. Dependencies start
at record +0x28; active bits are ORed into the low32 bits of record +0x20.

An implicit previous scheduler dependency follows the explicit ones. Its prior
comes from queue +0xa0 when cached, otherwise the native timestamp helper result
minus1, using the caller's command-record timestamp and index. It uses queue ID
low7 bits at bit40 and the prior's low47 bits. Tests cover 0..8 explicit entries,
not a protocol maximum. Valid event-index ranges remain unproven.

## QOS, register lists and notifications

Record +0x20 additionally carries QOS input byte0 at bits32..39, u32 input+8 low5
at bits40..44, and u32 input+4 low16 at bits48..63. Unspecified bits are retained.
The low2 bits of RCE input word0 replace the entire record byte +0x148.

Four RCE descriptors supply address/count at input +8/+0x10, +0x18/+0x20,
+0x28/+0x30, and +0x38/+0x40. Output words at +0x150/+0x158/+0x160/+0x168 encode
address>>5 low38 bits and count low7 bits at bit43. Bits38..42 are cleared;
high14 bits remain unchanged. These are seven-bit direct counts, not the separate
aperture's six-bit count-minus1 field.

Four notification words copy to +0x128/+0x130/+0x138/+0x140. Caller x5 is stored at
+0x178; its semantic meaning depends on wrapper provenance, and is not guessed.
DMB ISH precedes counter advancement. Actual LSE accounting increments pending
count and normal publication caches the original timestamp. The earlier accounting
audit covers the capacity-equality diagnostic branch; these body/composite cases
use old pending count below capacity and stop before the normal epilogue.

## Composition and practical boundary

The composite audit executes native instructions continuously from +0x89db298
through +0x89db5dc, following the dependency branches and helper calls. It validates
that aperture/header/payload, dependencies, QOS, descriptors, notifications and
publication compose for both cached and uncached paths. Manual input-register
fixtures represent the state after the external backing initialization call.

This closes the common encoder arithmetic gap for the tested input geometry.
It does not establish that zeroing is the external call's full effect, that the
fixtures represent valid 3D inputs, or that mapping/cache/firmware acceptance works.
The next implementation work is the CL/TA/3D wrapper input provenance and actual
hardware mapping/kick offsets. The retained failed warm probe still requires
reboot before hardware experiments.

Reproduce body/composite audits with the matched binary and an output JSON path:

```sh
python experiments/t6040-gpu/audit-private-work-body.py \
  /boot/GPUC003/private-apple/com.apple.AGXG16X /tmp/work-body.json
python experiments/t6040-gpu/audit-private-work-record.py \
  /boot/GPUC003/private-apple/com.apple.AGXG16X /tmp/work-record.json
```
