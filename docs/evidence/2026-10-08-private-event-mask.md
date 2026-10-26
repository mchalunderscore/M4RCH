# Native type1 firmware notification mask dispatch

Private-derived matched AGX353.14 / Apple25G83. No hardware changes.
The drainFirmwareEventRing switch table at89a3d38 binds type1 to89a2e50.
Native instructions89a2e50..89a2f64 execute in the offline audit; the stop
precedes the branch back to the general receive loop.

## Observed event fields and service calls

Within a72-byte general event entry:

| Offset | Width | Observed use |
| --- | --- | --- |
| 0 | u32 | Requires type1 |
| 4 | u64 | Notification bits0..63 |
| c | u64 | Notification bits64..127 |
| 14 | u16 | Must be below24 before any notification/time service call |

Offsets are hexadecimal. The small selector's semantic meaning remains unnamed.
The code obtains an external time-service value from b928a20 and stores it at
accelerator1aec0. For each set bit, it calls external service a7cf84c with
x0=accelerator140 event-machine object, w1=bit index0..127, w2=0. Four32-bit
RBIT/CLZ loops produce strictly ascending indices. There is no callback for
unset bits. The local stack4c accumulator ORs1 when either mask is nonzero.
The received event record and unrelated object fields remain unchanged.

These are event-machine notifications, not proof of a command fence. The
external service implementation is absent from this extracted driver, so the
subsequent event-machine/work-queue completion dispatch cannot be established
from this slice. Do not map a bit index directly to a GPU job ID or release a
command upon this event without establishing the associated event state.

## Verification and decoder integration

```
python experiments/t6040-gpu/audit-private-event-mask.py \
  /boot/GPUC003/private-apple/com.apple.AGXG16X \
  docs/evidence/2026-10-08-private-event-mask.json
```

1,024 cases pass:1,008 valid,12 rejected selector values and4 wrong types.
The valid cases generate56,385 checked callbacks and cover every single bit
position, zero masks, full masks and random masks. Independent bit enumeration
matches the exact ordered callback arguments; full accelerator, firmware and
stack fixtures match expected writes. Invalid branches stop before diagnostic
paths and produce no provider calls. Binary/slice hashes and switch target are
pinned. External time and event-machine service calls are synthetic.

The existing read-only receive13 decoder already extracted the observed masks.
The audit now cross-checks that decoder against native dispatch for each fixture.
Its new native_callback_indices field suppresses callbacks when selector>=24,
while preserving raw observed bits and reporting the selector bound separately.
Thus a snapshot can distinguish raw flags from flags the native guard accepts.
No cursor is written and no live firmware event is asserted by these fixtures.

## Next

Trace other event classes and scheduler counter updates, and obtain/inspect the
matched event-machine provider before claiming end-to-end completion delivery.
Continue real shader/render-target preparation in parallel with these missing
completion links. Retained warm INIT still needs normal reboot before hardware
experiments. No rendered pixels or GPU accelerated desktop are proved.
