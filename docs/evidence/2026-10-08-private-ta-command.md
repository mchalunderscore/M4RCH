# TA SKSM construction joined to native register output

Private implementation-derived AGX353.14/25G83 numeric work. Offline RAM only;
no live submission, kernel change, reset or reboot. No actual triangle yet.

`audit-private-ta-command.py` executes native slices and a continuous interval against independent
models in `private_ta_command.py`. Each passes1,024 cases comparing the entire
9c0-byte command and unchanged descriptor/context/stack sources. Serial-owner
backing is also compared in full, including u64 wrap. Adjacent JSON pins the
binary and each range. Offsets below are hexadecimal.

| Native slice | Checked behavior |
| --- | --- |
| 8a1f394..8a1f3f0 | Opcode0, unaligned serial at4, header fields, caller byte94d |
| 8a1f3f0..8a1f4d8 | Three translation calls and returned addresses at20/28/30 |
| 8a1f514..8a1f5d4 | Resource fields, packed epoch, metadata, context copies, clears |
| 8a1f6f4..8a1f76c | Explicit preceding branch result, stack/register metadata, descriptor copies |
| 8a1f5d0..8a1f76c | Notification/mapping arguments, address arithmetic and derived control/tail |
| 8a1f4d8..8a1f514 | Actual inherited submitted-kick counter callback |
| 8a1f394..8a1f76c | Complete continuous construction interval before register generation |

Owner lookup is an external fixture. Firmware translation virtual2d8 receives
descriptor1220/1228/1250 and W2=0 in order; argument identities and slot are
checked, but returned addresses are explicit fixtures. Authentication is skipped.
Descriptor virtual1a8 resolves through TA vtable7eb7560+10 to8987000,
`incrementSubmittedKicks`. The actual method increments the u32 pointed to by
descriptor198 with W1=1;1,024 cases check whole counter backing and wrap.
The continuous interval executes that method rather than substituting its result.

Notification virtual150 receives descriptor13f0, output pointer descriptor13e8
and W2=descriptor1274. Its descriptor13e8 write is an explicit external fixture,
not an established notification identity or lifetime. Mapping virtual158 receives
the object at descriptor1428->30->50. Its explicit return plus **unsigned u32**
descriptor1430 is stored unaligned at command945, wrapping u64 on overflow.
Other writes cover command934/93c/93d/8fe/892/89a. The caller's context flags
are reduced to bit0.

Control defaults to0. If accelerator6e0 is nonzero, context5c0 is1 or2 and
descriptor1130 is not3, accelerator mode1 uses `(context13f&1)^1`, mode3 uses1,
and other modes use0. Mode3 jumps to8a1fff4: exactly `mov w8,1` then a branch
back to the common tail. That native trampoline executes in62 cases;962 others
take the remaining paths. It is not a different submission route. The full
continuous preproducer interval passes1,024 whole-command/source/object checks.

Descriptor14e8 supplies low40 bits to command7a8 as a u64 and bits40..47 to
**both** command7b0 and7b1. High16 bits do not enter these fields. Caller X28
provides command94d and90e; it differs from the register producer's
descriptor190 lookup context. Do not silently substitute one for the other.

## Reusable composition

`prepare-native-sksm-registers.py` accepts optional `ta_construction`:

```json
{
  "submit_context": "submit-context.bin",
  "submit_stack": "submit-stack.bin",
  "serial": "0xffffffffffffffff",
  "firmware_translations": ["0xffffffb000100000", "0xffffffb000108000", "0xffffffb000110000"],
  "x26": "0xffffffb000100100",
  "w21": 0,
  "w22": 1,
  "completion_mapping_address": "0xffffffb000120000",
  "accelerator_mode": 0
}
```

Context must be600 bytes and stack100 bytes. Translation addresses, serial and
X26 and completion mapping are explicit u64; W21/W22/accelerator mode are u32. They are caller fixtures,
not inferred valid resource identities. Boolean integer inputs are rejected.
The models operate on actual TA register-producer output and export a separate
`ta-construction-candidate.bin`, preserving producer-only output.
Register backing and metadata60..77f must remain byte-identical.

Sixteen paired cases pass, retaining80 list/scheduler links and64 independently
expected firmware register values. Checks cover serial, three translation
results, packed epoch boundaries, caller context/stack metadata, mapping-offset
wrap, all16 accelerator-mode/context combinations and preservation of register
output. Caller-supplied branch results are rejected: control is derived.
Eleven malformed inputs fail before export. All receipts
retain `submission_ready=false`.

Remaining: actual completion mapping/notification service semantics and other
command fields; initialized resource
identities; Linux physical backing, mapping/cache, publication, completion and
coherent readback. Retained failed warm INIT requires normal reboot before
live integration.
