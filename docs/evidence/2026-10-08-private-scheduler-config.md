# Native scheduler configuration command prefix

Private-derived matched AGX353.14 / Apple25G83. No hardware execution.

`AGXCommandDescriptor::initKSMKickQueueConfigUpdateCommand` constructs a packed
opcode-15 record. Three call-free store slices in this function establish:

| Offset | Width | Source/value |
| --- | --- | --- |
| 0x00 | 8 | Constant 15 (opcode u32 plus zero next word) |
| 0x08 | 16 | Scheduler queue object +0x80/+0x88 pair |
| 0x18 | 2 | Low 16 bits of scheduler queue +0x0c |
| 0x1a | 4 | Descriptor +0x181 bit0 |
| 0x1e | 4 | Scheduler queue +0x1c |
| 0x22 | 4 | Descriptor virtual getDataMaster() result |
| 0x26 | 4 | Zero |
| 0x2a | 8 | Zero |
| 0x32 | 4 | Descriptor +0x144 |
| 0x36 | 16 | u64 zero followed by u64 all ones |
| 0x46 | 4 | 0xffffffff |
| 0x4a | 8 | Zero |
| 0x52 | 8 | Zero |
| 0x5a | 8 | Zero |
| 0x62 | 4 | Descriptor +0x180 bit0 |
| 0x66 | 4 | Descriptor's +0x58 object's virtual +0x1e0 result |
| 0x6a | 4 | Zero |
| 0x6e | 16 | Same zero/all-ones pair |
| 0x7e | 8 | All ones |

These writes cover exactly 0x86 bytes. The uploaded spec's 0x88-byte allocation
is consistent, but final two bytes and independent allocation-size proof remain
unqualified here. Model helpers preserve every byte outside the observed
prefix, rather than assuming implicit zero padding.

## Source qualifications

The first callback is named getDataMaster. In the inspected CL, TA and 3D
command-descriptor vtables, slot +0x188 resolves to native functions returning
0xff. The checker pins each target and its constant return instruction.
Do not substitute accelerator-ring engine codes 0/1/2 into this field simply
because it has a related name; class overrides and caller context must match.
The second callback's implementation and semantic role remain unresolved.

Scheduler queue +0x80/+0x88 come from distinct mapping subobjects of the same
internal resource during AGXKSMKickQueue::init. Queue +0x78 is its CPU backing
mapping. Initializer arguments also populate capacity +0x10, stride +0x14,
queue ID +0x0c, accelerator pointer +0x68 and counter fields +0x48/+0x50.
This narrows provenance; mapping modes/cache policy must still be established.

## Verification

`audit-private-scheduler-config.py` executes only the three reviewed store
slices with real file-backed constants. External calls/PAC sequences are not
executed; callback values are supplied independently. The numeric model in
`private_scheduler_config.py` agrees for 256 randomized cases, including flag
masking, identifier truncation, packed unaligned fields, callback 0xff cases,
and preservation of output tail bytes. It pins matched binary SHA and slice
hashes, and three descriptor vtable/return sites.

No native service, resource allocation, complete descriptor construction,
firmware acceptance or live scheduler setup is validated by this test.

Next qualify the mapping pair, second callback and configuration-command
allocation, then finish dependency/event-mask NOP construction. Current failed
warm probe remains retained; normal reboot is needed before hardware tests.
