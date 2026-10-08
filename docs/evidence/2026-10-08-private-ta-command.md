# TA SKSM construction joined to native register output

Private implementation-derived AGX353.14/25G83 numeric work. Offline RAM only;
no live submission, kernel change, reset or reboot. No actual triangle yet.

`audit-private-ta-command.py` executes four native slices against independent
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

Owner lookup is an external fixture. Firmware translation virtual2d8 receives
descriptor1220/1228/1250 and W2=0 in order; argument identities and slot are
checked, but returned addresses are explicit fixtures. Authentication is skipped.
Descriptor virtual1a8 at4d8..514 is excluded, as are completion-resource
operations and conditional control between5d4 and6f4. That branch's result is
supplied explicitly, not independently derived.

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
  "branch_result": 0
}
```

Context must be600 bytes and stack100 bytes. Translation addresses, serial and
X26 are explicit u64; W21/W22/branch result are u32. They are caller fixtures,
not inferred valid resource identities. Boolean integer inputs are rejected.
The models operate on actual TA register-producer output and export a separate
`ta-construction-candidate.bin`, preserving producer-only output.
Register backing and metadata60..77f must remain byte-identical.

Sixteen paired cases pass, retaining80 list/scheduler links and64 independently
expected firmware register values. Checks cover serial, three translation
results, packed epoch boundaries, caller context/stack metadata and preservation
of register output. Eight malformed inputs fail before export. All receipts
retain `submission_ready=false`.

Remaining: excluded descriptor callback, completion-resource/notification
binding, conditional control and other command fields; initialized resource
identities; Linux physical backing, mapping/cache, publication, completion and
coherent readback. Retained failed warm INIT requires normal reboot before
live integration.
