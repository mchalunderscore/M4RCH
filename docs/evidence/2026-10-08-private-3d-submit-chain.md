# Connected native 3D configuration, scheduling and post-kick chain

Private-derived matched AGX353.14 / Apple25G83, offline only. The native caller
now runs continuously from895bd00 through895c374: configuration construction /
publication, scheduling NOPs, actual3D entry, owner callback and post-kick record
publication. Scheduler return and count are produced natively rather than
supplied to the post-kick encoder.

## Covered chain

1. Inline opcode15 configuration construction, including scratch fields,
   conditional state and owner/channel fields. Actual native publisher appends
   descriptor468 GPU address to the channel pointer ring.
2. Native calculation/guard of extra scheduling NOP count. Complete native NOP
   methods encode and publish all padding entries.
3. Complete native3D wrapper/common encoder creates the actual3D scheduler
   entry. Native caller saves its real timestamp return and increments the
   descriptor2dc count after adding the NOP count.
4. Actual owner lookup and virtual168 call with queue ID and scheduler20 value.
   Provider behavior is synthetic; no unsupported meaning is assigned to the
   callback beyond the inspected argument contract. Caller sets descriptor2f5=1.
5. Optional opcode12: queue ID, actual timestamp and mapped descriptor910 value.
6. Mandatory opcode14 (acceleratoree5f bit0 clear): queue ID, descriptor2dc low16,
   priority low8, actual timestamp and constant1. This count is extra+1 in the
   fixtures, not a supplied synthetic count.
7. Optional opcode16: queue ID, same actual timestamp and constantfe.
8. Each control record enters actual writeChannelCommandPointer, which appends
   its GPU address and advances producer40. Configuration precedes opcode12,
   opcode14 and opcode16; absent optional records do not publish pointers.

## Combined verification

```
python experiments/t6040-gpu/audit-private-3d-submit-chain.py \
  /boot/GPUC003/private-apple/com.apple.AGXG16X \
  docs/evidence/2026-10-08-private-3d-submit-chain.json
```

1024 connected cases pass:

- 1024 configuration records;
- 34943 actual native NOP records and1024 actual native3D scheduler records;
- 512 opcode12,1024 opcode14 and512 opcode16 records;
- 3072 actual native pointer-ring publications, including cursor wraparound;
- 64 invalid padding-count guards before scheduler/post-kick emission.

Independent models compare entire scheduler backing, queue/descriptor state,
configurationc0 and control40 backing including preserved tails, exact control
publication order, pointer-ring/state bytes and actual timestamp/count values.
All optional combinations, conditional configuration branches and high mask flags
are covered. Prior cached/uncached conversion, QoS branches and auxiliary-value
sources are retained from the earlier full scheduler audit.

## Explicit simulated release balance

After inspecting each emitted chain, the checker explicitly invokes native
completion counter slice895e1ac..895e1f8. Descriptor964 selects the synthetic
scheduler whose pending count is extra+1; descriptor2dc releases exactly that
count. Pending44 returns to its initial zero and descriptor144 becomesffffffff
in all1024 cases. Full object comparisons verify the resulting changes.

This deliberately simulated completion is not firmware-triggered. It proves
accounting balance between native publication/count accumulation and the native
release slice, not notification routing, valid job completion or fences. The
synthetic table aliases event-index and descriptor/original queue identities;
it does not establish valid real-world identity relationships.

## Limits and retained gaps

The test starts after allocation, record-pointer selection and render/shader/
target preparation. Config conditional x26/w27 inputs and scratch value already
in descriptor2e8 are supplied; their individual producers have earlier audits.
Native getDataMaster/payload/event getters, actual scheduler encoders, DMB/LDAR/
LSE instructions and pointer publisher execute. PAC is bypassed.

Owner lookup, owner callback, descriptor58/channel170 callback returns, firmware
mapping and zero-memory services use explicit synthetic contracts. Firmware
mapping receives the actual descriptor910 argument but supplies its GPU address.
Acceleratoree5f-set host-tracking path and optional provider-assisted tracing are
not covered. Guard fixtures start at895bfc8, after configuration publication;
they prove no scheduler/post-kick emission at that boundary, not rollback of an
already published configuration.

No full submit function, actual allocation lifetime, hardware doorbell, DMA/cache
or concurrent operation, firmware acceptance, completion notification, fence,
shader execution or rendered pixels is proved. No private code is exported.
No kernel/default or hardware changes; retained warm INIT still needs normal
reboot before new hardware trials.

## Next implementation work

This supplies a connected byte-level submission reference and count/publication
contract. Next resolve native resource preparation and kick/doorbell mapping
provenance, plus the firmware completion consumer that selects a live descriptor.
The checked builders can then inform a bounded first-job implementation rather
than being treated as sufficient evidence for a live draw. An executable shader,
render target and reliable completion path remain the triangle prerequisites.
