# Continuous ordinary3D construction joined to paired candidates

Private implementation-derived AGX353.14/25G83 numeric work. Offline Unicorn
RAM only. No driver loading, live GPU command, reset or rendering claim.

Actual continuous895b388..895b9d8 compares entire2300-byte command backing,
1800-byte descriptor, body source, channel, serial owner, submitted-kick counter,
PM-operation counter and caller stack against independent models in1,024 cases.
This backing extent is an audit fixture; candidate output uses previously
qualified ordinary host stride2240. Full register producers remain separate.

Actual inherited descriptor1a8 executes8987000 and increments the u32 at
pointer198. Actual descriptor1f0 executes895d5c0 and increments the u32 at
pointer940. Native slot220 on the G16_SKSM3D channel resolves89d5cf0 and reads
byte204. The body first increments u32 channel204; the tail uses its new low8
bits at command90. Deliberate wrap cases cover all three counters and serial.
This resolves the former synthetic tail callback result. These callback targets
are verified from the native vtables; method hashes are in the adjacent JSON.

The command gets descriptor188 at20, then explicit translation results at
28/30/38. Firmware virtual2d8 receives descriptor908/910/938 with W2=0.
Translations remain external service fixtures; no real physical/FW maps proved.

Descriptorb70 gates notification/mapping.512 present cases invoke notification
virtual150 with objectb58, output pointerb50, descriptor144; mapping158 receives
objectb90->30->50. Its explicit return plus **unsigned u32** b98 wraps u64 and
writes unaligned command21df.512 absent cases leave that command field unchanged.
Flagb9c&1 writes21d6; descriptorba0 writes21d7. Both conditional paths are checked
in the continuous interval. Notification outputb50 is a fixture mutation, not
verified lifetime/retirement. Authentication bypassed; owner lookup external.

## Reusable paired construction

Optional `3d_construction` in prepare-native-sksm-registers.py:

```json
{
  "body_source": "3d-source.bin",
  "frame_data": "3d-frame.bin",
  "submit_stack": "submit-stack.bin",
  "serial": 0,
  "channel_counter": 0,
  "w21": 0,
  "w22": 0,
  "firmware_translations": ["0xffffffc000000000", "0xffffffc000010000", "0xffffffc000020000"],
  "completion_mapping_address": "0xffffffc000030000"
}
```

Body source400 bytes, frame24 decimal bytes, stack100 hex bytes. Addresses/
serial u64; counter/W21/W22 u32. Boolean integers rejected. Callback/payload
inputs rejected because the byte derives from the counter. Independent caller
serial inputs do not establish ordering through a shared live serial owner.

The builder composes header/resource/body/tail models over actual native
four-list producer output and exports3d-construction-candidate.bin. Every actual
register backing range and its12-byte metadata must remain unchanged. The
receipt records counter before/after and scratch payload.16 pairs pass resource,
frame/body/stack/payload and list-preservation checks;80 list/scheduler links
and64 independent TA firmware values remain checked.15 malformed inputs fail
before export. Every receipt remains submission_ready=false.

The64 native descriptor-preparation cases now also produce partial3D commands.
They use explicit body-source/frame/stack/service fixtures, not a proven complete
submit caller or Linux-owned graph. Existing whole TA producer equality and320
intermediate comparisons,256 FW-address and5248 entry comparisons still pass.

Remaining: ordinary3D event timestamp/control construction895b9d8 onward,
pre-register flags, post-register aperture records and channel scheduling/
publication, real Linux allocations/address domains/cache visibility and
completion/retirement/readback. Current header/body/tail assembly must not be
mistaken for a complete initialized channel command. No triangle submitted.
