# Reusable native common scheduler work preparation

Private-derived numeric ABI model; no GPU or kernel activity.

native_scheduler_candidate.py now serializes the checked native common scheduler
prefix, dependency/body and accounting updates from an explicit JSON binding
manifest. It outputs work-common.bin (200 hexadecimal bytes), a host accounting
fixture and a receipt. The common record is distinct from the TA/3D work objects
and their microsequences; it must not be submitted as a replacement for either.

The serializer preserves an optional original record's unknown fields, enforces
representable narrow IDs/counts/QOS,32-byte pointer alignment, coherent pointer/
count presence and qualified dependency/capacity ranges. It rejects a full queue.
JSON floating-point values and booleans in integer fields are rejected to avoid
silent truncation. Timestamp/address source scalars still follow the checked
native bitfield arithmetic; high address prefix normalization is not qualified
merely by encoding the low-field representation.

The explicit manifest supplies:

- Queue ID, priority, timestamp, capacity, previous dependency, initial epoch and
  pending count. It does not allocate or register a queue.
- Aperture address/index/count, two payload words, four notification words,
  auxiliary address and two header flags.
- Zero to eight event dependencies, each with timestamp/index/selected epoch.
  The existing qualification uses event backing indexes0..23, not a proved limit.
- QOS, RCE kind and four ordered register-list address/count pairs. No count is
  inferred from a backing-buffer length; our checked3D export counts87/16/23/10
  are supplied explicitly in the illustrative numeric fixtures.

A new direct native check runs128 complete actual-driver prefix/body/accounting
constructions with matching manifests and random original record contents.
Dependencies0..8, capacities1/2/3/16/256, flags and representable narrow fields
vary. Every whole record and changed accounting field matches. This uses cached
previous dependencies; the earlier native composite audit also covers uncached
conversion, which is not implemented as a manifest-free lookup here.

Three validation test methods cover a valid zero-backed record and26 invalid
input mutations/dependency geometries. Invalid aperture alignment is checked
only when that aperture is active, matching the serializer's contract.

```sh
python experiments/t6040-gpu/native_scheduler_candidate.py \
 EXPLICIT_BINDINGS.json NEW_OUTPUT_DIRECTORY
python experiments/t6040-gpu/check-native-scheduler-candidate.py \
 /boot/GPUC003/private-apple/com.apple.AGXG16X NATIVE_CHECK_RECEIPT.json
python experiments/t6040-gpu/native-scheduler-candidate-tests.py
```

An illustrative candidate was generated under/tmp/native-scheduler-prepared-20261008
from the native-check fixture; its common work SHA256 is
69e1995f97cc43a045c571985b5ccccfdf67f7198e2d84c5ed0c05d2ba6c768d.
Those addresses/scalars are numerical inputs, not established live allocations.
The output always says submission_ready=false. The queue output is a host fixture,
not a complete initialized firmware queue or a command that can be published.

Remaining live integration: validated queue/root/resources, matched TA/3D work
and microsequence/lifecycle bindings, cache-visible publication, independent
firmware/event/stamp completion and coherent readback/retirement. This tool
makes the common encoder reusable but does not close those gaps. The failed
warm INIT remains retained; normal reboot is required before live testing.

Only our numeric serializers, binding examples and receipts are exported;
no Apple executable code is included. This is private implementation-derived
research, not a clean-room specification. No public push performed.
