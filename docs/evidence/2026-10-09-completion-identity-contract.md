# Completion identities and retirement boundary — 2026-10-09

Offline analysis of the pinned Apple25G83 / AGX353.14 driver, matching firmware
TEXT, saved audits and `out/recovery-dispatch/prepared`. This adds identity and
ownership obligations, not completion, rendering, reuse or release permission.
The current sealed instance and prepared candidate were not changed.

The companion JSON is reproducible with:

```sh
python3 experiments/t6040-gpu/analyze-completion-identities.py \
  /boot/GPUC003/private-apple/com.apple.AGXG16X \
  out/recovery-progress/candidate/asc-graph-init/boot-1730bf24-0823-4be9-a338-7e136762d076/text.bin \
  out/recovery-dispatch/prepared \
  out/completion-identities/audit.json
```

Private driver SHA256 is
`3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e`;
normalized firmware TEXT SHA256 is
`190cef1946a23dfbde180592629631c3b28d0509a17eb76108b7c9a52accd9ac`.
The script verifies both identities, reused proof slice hashes, prepared graph,
backing and command hashes. Only numeric research is exported; binary and full
disassembly remain private. Offsets and addresses below are hexadecimal.

## Identities that must remain distinct

| Identity | Locally established meaning | Missing association |
| --- | --- | --- |
| KSM queue ID | Header/firmware completion extraction has seven bits, 0..127 | Allocation/registration to a host channel and stamp index |
| KSM timestamp | Low40 timeline plus additional payload bits; queue capacity/initial and event epoch affect conversion | Original event stamp and epoch ownership across wrap/recovery |
| Hardware completion descriptor index | Four 32-byte routing descriptors at hardware+2620, indices0..3 | Which routing ring delivers an eligible command completion |
| Type1 notification bit | 128-bit mask dispatched as indices0..127 to the event-machine object | Pending command, workqueue, fence, error callback and retained resources |
| Type1 selector | Separate u16 at event+14, native guard<24 | Complete meaning; it is not the notification index |

The prepared fixture has TA queue0 and 3D queue1, both KSM timestamp1 and
command timestamp1. Their firmware command addresses are
`fffffc2000802240` and `fffffc2000800000`. This is a checked equality within
the fixture, not event-machine registration. The four hardware routing rings
are another identity domain. A matching number is insufficient to join them.
The prepared ordinary3D completion record+2140..215f is entirely zero, including
raw operand+2150 and raw index+2154, and optional mapping+21df is zero. TA's
separate mapping field+945 points to `fffffc2000b14000`. Neither that mapping
nor timestamp equality supplies the missing host event/fence ownership.

## Exact local command and notification paths

Native ordinary3D construction `895b9d8..895bbb0` obtains the descriptor event
record through the actual getter `895d5e4` returning descriptor+210. It reaches
the selected queue through accelerator+f938[index*8], then queue+68 -> owner+140
event machine. `895ba7c..895ba98` selects machine+1458 or+1460 plus index*18;
selection includes the signed CMN/CSEL boundary behavior. Queue+10 capacity and
queue+90 initial value participate in conversion. `895badc..895bae4` combines
the channel payload at bit40 and publishes the result to descriptor+178 and
command+2160. The existing 2,048-case audit checks this construction against
independent arithmetic; queue, epoch and event providers are still fixtures.

Firmware `12788..12850` extracts seven-bit queue ID, phase, 40-bit epoch and
masked metadata from a **64-byte hardware completion entry**. It prepares a
four-byte range at entry+30 with its low pointer flag cleared, then reads the
u32 there. Subsequent `12bdc..12dd0` dispatches on that u32 as command class;
class1 requests the full2240-byte ordinary3D command. Therefore the prefix's
four-byte read must not be treated as an independently verified fence stamp.
The ordinary3D later path reads command+2160 at1459c and stores it at
13c3a0+completion_queue_id*8 at145e0. That is a concrete command/timeline link;
it does not establish successful draw completion or client callback delivery.
Entry+38 receives an a8-byte cache request and is a separate context pointer.

A distinct **class0x11 (decimal17)** path (`12d20..12d98`) selects command+4 as a small
payload, later restored through stack+90 at14c94. `14d14..14d18` selects its
terminal notification path. At15070..150ac the payload contains:

| Payload offset | Use |
| --- | --- |
| 0,u64 | Destination of a u32 store |
| 10,u32 | Stored value |
| 14,u32 | Index used to construct the 128-bit notification mask |

The direct path performs the store, a DSB and calls32bac with the two mask
words. New RAM checks cover all128 valid indices and eight u32 boundaries:
1,024 whole-memory comparisons pass. They begin at15070; **eligibility and the
intervening completion handler are not emulated**. No assertion says the
ordinary TA/3D job takes this class17 path.

Static firmware32bac..32ce8, with pending metadata absent, constructs general
event type1, puts masks at+4/+c and selector0 at+14, publishes the72-byte record
through main+1c0/+1c8 and sends EP32/class42. This is not another64-byte hardware
completion entry. The actual native type1 dispatcher89a2e50..89a2f64 calls
a7cf84c with accelerator+140 event-machine object, ascending set-bit indices
and third argument0. Its existing 1,024-case audit verifies56,385 callbacks,
the selector guard and all128 one-hot positions. The **external event-machine
implementation is the hard boundary**: no command/fence completion follows
from a mask alone in our established contract.

## Stamp arithmetic and retained resources

Native `AGXEventMachine::writeStamp`899f564..899f620 writes `(stamp,index)` to
the supplied command record and clears the selected slot at
machine+2254+index*400+(((stamp>>8)&ff)*4), using the native256-slot count.
Its current-stamp row is machine+1450+index*18; sign crossing updates one of
the companion epochs. New RAM checks cover128 indices × eight stamp
boundaries:1,024 whole-memory matches, including512 sign crossings. The
successful fast path requires new==prior+100 modulo32; the exceptional path
is excluded. These are host event-stamp values, not KSM timestamp1 directly.

`forceCompleteStamp`899f424..899f4e8 accesses accelerator+580/+588 u32 arrays.
It advances both only when signed32(new-old)>0, then calls a7cf84c with the
current value and a7f9308 on the accelerator. New1,024 complete-method RAM
checks include416 advances and stale/half-range/wrap boundaries. Provider
calls are recorded. A forced stamp update is not an observation of hardware
completion and must not be used to bypass the missing completion chain.

Native retained lookup8979928..8979a10 searches channel+18 against the stamp
index through candidate workqueue+218/+220 and invokes virtual retain+20.
Enumeration and casts are external; its callers supply the stamp index.
This supplies a concrete host ownership mechanism, not a proof that our chosen
KSM IDs0/1 are registered stamp indices. Undefined imports include stamp
registration/channel lookup, event tests and
`IOGPUWorkQueue::findCommandDescriptorWithStampValue`; their implementations
and the exact imported-address bindings are outside this audit.

Completion callbacks also have resource work. Command-buffer complete
89877b8..8987880 obtains internal resources+30/+278, locks resource+40 and,
when resource+38>=1, calls external a8032b4 on nonnull mappings+50/+58 before
decrementing+38. Ordinary3D complete895dca4 starts with descriptor+1c2 bit0,
handles pool accounting and mapping completion; tail895e268..895e2ac handles
another internal resource's maps+50/+58 and reference count. These reviewed
bodies are not an end-to-end callback proof. The extracted driver does not
prove the external mapping operation's unmap/destruction/cache/DMA semantics.

`AGXWorkQueue::handleIOFenceComplete`8a2e0a8..8a2e2e8 receives an explicit
AGXIOFenceData pointer, checks and unlinks its+a0/+a8 list links, adjusts
workqueue+e0 and records external time at workqueue+f8. The head-fence path
tail-dispatches workqueue virtual+1b0 with that same fence pointer. The trigger,
virtual target and final fence/resource lifecycle remain outside this focused
qualification. This is additional host bookkeeping that cannot be replaced by
observing a firmware queue cursor or one notification bit.

## Concrete implementation obligations

1. Keep an owned host registry linking **stamp index, channel, workqueue,
   command, generation and retained resources** before publication. KSM queue
   IDs and routing-ring indices remain separate keys until explicitly joined.
2. Preserve the original event stamp, selected epoch, queue capacity/initial,
   packed timestamp/payload and command device/FW mapping identities. Compare
   wrap-aware generations, not plain integer equality or cursor advance.
3. Decode completion routing records and the matching command class, then read
   its completion state coherently. Reject stale, duplicate, ambiguous and
   error records without retiring the wrong command. A transport notification
   or matching low40 timestamp is only an intermediate observation.
4. Qualify a host callback/fence dispatcher that joins the exact pending
   command and delivers completion/error once. The missing external Apple
   event machine does not prevent implementing a Linux equivalent, but its
   behavior cannot be invented from notification bits alone.
5. Balance retained mappings/resources only after independent queue/context
   and DMA retirement. Successful RTKit shutdown, forced stamps, idle recovery
   or changed memory do not substitute for that contract. Post-work recovery
   requires the separate submitted-timestamp/TA recovery bookkeeping contract.

The analyzer always emits `completion_verified=false`,
`retirement_verified=false` and `resource_release_authorized=false`.
No hardware, sysfs, live acknowledgement, resource reuse or freeing occurred.
