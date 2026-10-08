# Native parameter-manager and hardware-buffer reset

Private-derived AGX353.14 / Apple25G83, offline RAM. Complete
AGXParameterManagement::resetParameterState (89fb670..89fb720) executes the
actual nested AGXHWParamBufferManager::resetHWParamBufferState
(89fb720..89fb8f4). No live GPU command, allocation or kernel change.

512 complete PM+HW cases and512 HW-only cases match independent whole-object
models. Comparisons cover the PM object, configuration with embedded PM state,
HW manager, HW state and auxiliary counter, preserving every unmodified byte.
The conditional PM request is exercised256 times. Original state bytes and
provider returns vary, including u32 truncation and shift overflow.

## PM reset

PM+130 supplies the external lock/unlock object. PM+80 points into its
configuration object at config+40 in this fixture. Reset clears its four u32
words0/4/8/c and stores1 at state+20, sets PM+28 byte1, copies config+8 u32 to
PM+140, then resets the actual manager at PM+20. If manager+30 is nonzero it
calls PM virtual1c8 with a pointer to a copy of config+4 u32, before unlocking.

The virtual call and lock services are explicit fixtures, not the real provider
implementations. A successful numeric reset does not prove that an arbitrary
configuration/capacity or PM subtype is valid for rendering.

## Hardware-buffer state

Manager+48 points to the output state; manager+98 points to PM; manager+50
points to an auxiliary u32 counter cleared here. All table offsets hexadecimal.

| State offset | Width | Source/value |
| --- | --- | --- |
| 0 | 8 | zero |
| 10 | 4 | PM+1d4 u32 |
| 14 | 8 | zero |
| 20 | 8 | translated first resource-map result |
| 28 | 8 | second resource-map result |
| 30 | 4 | low32 of support object+78 qword |
| 34 | 4 | zero |
| 38 | 4 | PM+148 u32 |
| 3c | 8 | zero |
| 44 | 8 | PM+c0 qword |
| 4c | 8 | PM+c8 qword |
| 54 | 4 | ffffffff |
| 58 | 4 | low32 of PM+70 qword |
| 5c | 8 | zero |
| 64 | 8 | manager+60 qword |
| 6c | 16 | zero |
| 7c | 4 | PM+15c u32 shifted2, modulo2^32 |
| 80 | 4 | PM+154 u32 shifted2, modulo2^32 |
| 84 | 8 | PM virtual208 result |
| 8c | 4 | zero |

Gaps are preserved. Manager+34..43 is cleared separately. Those are host-manager
fields, not additional bytes in the output firmware-visible state. State10 and14
are intentionally adjacent despite the unaligned qword at14.

Service order:

1. Resource from manager+28: virtual158 returns mapA.
2. Scheduler from manager+18 -> object+5b0: virtual2d8(mapA,0) returns the value
   stored at state20. MapA is not directly stored there.
3. Resource from manager+20 -> object+20: virtual158 returns mapB, stored at28.
4. PM virtual208 result goes to84.
5. Optional PM virtual1c8 occurs only in the enclosing PM reset, after HW reset.

Arguments and call order are checked; maps, translation, optional request and
lock/unlock use explicit no-op/result services. Their actual address-space,
cache, lifetime and registration semantics remain external and must be connected
to our live root. Neither a resource-map pointer nor CPU object address should be
silently substituted for the translated result.

## Relation to scene and descriptor preparation

The previous PM scene slice supplies indexed vectors88/a8, records with80-byte
stride and config/state pointer80. Descriptor loaders consume those vectors and
three subtype getters; they do not initialize the HW state themselves. This
reset fills another required state layer and identifies four separate mapped
inputs. It does not yet qualify the full preceding PM allocator, resource
registration, scene/HWPB association or ordinary-subtype getter implementation.

Next connect the checked scene producer and HW reset to actual PM creation and
resource allocation, then tie the matched work to root, KSM queue, events/stamps
and coherent completion readback. The retained failed warm INIT still needs a
normal reboot before a new live GPU session. Offline work remains possible.

```sh
python experiments/t6040-gpu/audit-private-pm-reset.py \
 /boot/GPUC003/private-apple/com.apple.AGXG16X NEW_RECEIPT.json
```

The independent numeric models are in private_pm_reset.py. No Apple executable
code is exported. This is private implementation-derived research, not a
clean-room specification or proof of a submission-ready render job.
