# Connected primary native 3D SKU stream through finalization

Private-derived AGX353.14 / Apple25G83, offline emulated RAM only.
1024 continuous cases execute89d5344..89d5990 plus the complete native
encodeTimeStamp and finishEncode methods. This joins earlier isolated audits:

1. Native startup payload construction, resource translation and opcode7 copy.
2. Optional native beginning timestamp3, selected by descriptor893 low bit.
3. Channel virtual258 callback with saved firmware-address argument.
4. Optional native ending timestamp3, selected by preexisting stack20 low bit.
5. Native primary opcode8 end record, including notification-vector selection.
6. Native finishEncode appends40000002, advances cursor, rounds size to64 bytes,
   obtains/maps the stream address, and the caller publishes command14/1c.

Whole stream backing and encoder match independent composition. Descriptor
remains unchanged; the whole resulting command matches the original plus its
pointer/size publication. Timestamp encoders execute their actual code rather
than a supplied timestamp callback. Across the fixtures:1024 startup records,
1024 total timestamp records (all four presence combinations),1024 end records
and1024 finalizers. Entry counts0..16 have safe fixture backing, not a newly
proved hardware/protocol maximum.

The end timestamp record is encoded before opcode8 in this native primary
path. This is recorded CPU construction order; it is not a claim about GPU
execution timing or semantic equivalence to another generation's microsequence.
No leading/trailing wait is selected; optional secondary phase is explicitly
disabled. No actual beginEncode pool selection runs in this joined slice.

Resource type/address services, firmware address translation, memcpy and channel
callback are explicit stubs. memcpy checks the exact startup byte-copy contract;
channel258 supplies no-op behavior and is not a proof that its real effects are
unnecessary. Mapping uses a synthetic affine address translation; it does not
establish UAT permissions, cache policy, lifetime or live address domains.
PAC is bypassed for unsigned fixtures. Native trace/log mode is disabled.

This closes the primary stream's numerical composition and final pointer/size
publication gap. It does not make a valid draw: input command/descriptor bytes
remain numeric fixtures, and register/shader/target/parameter resources are not
allocated to live GPU addresses. Actual firmware interpretation/completion,
optional phase behavior and submission readiness remain unproved.

```sh
python experiments/t6040-gpu/audit-private-sku-stream.py \
  /boot/GPUC003/private-apple/com.apple.AGXG16X STREAM_RECEIPT.json
```
