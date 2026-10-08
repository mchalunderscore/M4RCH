# Native PM creation, resource binding and initializer

Private-derived AGX353.14 / Apple25G83, offline RAM only. No live allocation,
GPU command, kernel/default change or reboot. Models and receipts accompany this
note; a successful native control-flow fixture is not a working live PM object.

## Allocation prelude

The complete initializer prelude89fc624..89fc948 passes1,024 independent
whole-object comparisons. Slot/manager counts0..32 and state counts0..7 cover
both override/fallback paths and both memory-provider argument selections.
The vectors are checked byte-for-byte;261,888 bytes are cleared.4,608 state
initializer calls are checked, with no-op service effects explicitly supplied.

Three counts remain distinct:

| Count | Native source | Backing requests |
| --- | --- | --- |
| Scene/vector slots | GPU f528 if nonzero, otherwise718 | Two vectors of count*8 |
| State entries | GPU f52c if nonzero, otherwise71c | count*40 bytes, one state-init call per40-byte entry |
| Hardware-manager capacity | low32 of memory-provider result shifted17 | capacity*40 backing plus capacity*8 vector |

All offsets hexadecimal. Allocation prelude also allocates three lock/state
service objects and initializes explicit PM fields. It copies48 bytes from the
device configuration to PM1d8, queue configuration data to64/118, stores slot
capacity at b0 and the two vectors at a8/88. Negative capacity, allocation
failure and replacement of an existing non-null a8 vector are excluded.

Inherited initialization, allocation, locks, memory query and state-init are
external fixtures. Requested sizes, return-object binding and call order are
checked, not their real provider implementation or backing initialization.

## Three resources and registration

256 joined native cases run89fc624..89fd040 continuously: prelude, resource
creation/association, registration, scene-vector initialization and publication.
They compare the complete PM object, both vectors, scene buffers and scratch.
768 resource creation calls and4,224 scene records are checked.

Pinned native constant pair at712dee0 supplies PM70=20000 and PM78=8.
Three resource size requests are:

1. `40 | (slotCount << 7)`, i.e.40-byte header plus80 bytes per slot for these
   bounded counts. Resource object is published at PM38.
2. 80 bytes. Resource object is published at PM40.
3. `PM78 * managerCapacity`, therefore8 bytes per manager in this binary.
   Resource object is published at PM30.

Each initInner call receives the same GPU object and flags `GPU18e00 | 63`.
The tests use GPU18e00=0. Resource50 and60 mapping objects already exist in
these fixtures; lazy mapping creation, retain/release and failure paths remain
outside the qualification. The resource's10 type word is written by native code.

Registration requests use queue configuration28. The following provider method
receives PM and PM48 and three output pointers. Its explicit service fills a
registration ID at48, a CPU scratch pointer and two firmware scene bases. These
are external effects the actual provider must supply; they are not optional.

Resource50 virtual158 and resource60 virtual138 returns are used as CPU pointers
by the native host code in this path. The former begins vectorA's80-byte records;
the latter begins vectorB's80-byte scene records. Their values differ from the
firmware bases written at each scene's0/8. Virtual slot numbers alone do not
identify an address domain across different object classes.

The second resource's50 return becomes PMc8; its60 return becomes PM98.
PMa0=c8+40 and PM80=98+40. The vectorA end becomes PMb8. This connects the
previous isolated scene-array producer to actual caller/provider data flow.

## Complete initializer return

128 additional cases execute the entire native initializer through its normal
return at89fd390, with restored stack and result1. Full PM/vector/scene/scratch
comparisons include the final c0/90 mapping pointers,160 flag bits,164/168 zeros,
14c rounded memory limit,154/158/15c queue thresholds and150 zero. Three GPU
statistic registrations receive threshold*20000 byte values with argument20.

This uses the positive-capacity, preexisting-map, null-old-manager success path.
The final PM virtual150 readiness method and createNewHWPBManager call remain
explicit services. The latter supplies a manager pointer at20. Consequently the
whole initializer's checked control flow does not prove a real hardware-manager
allocation or usable live parameter manager. PM readiness, resource registration,
lifecycle/allocator semantics and live root binding remain prerequisites.

The harness reuses the creation audit's modeled loop, with explicit additions
for the complete tail. Its code/source ranges are hash-pinned. No Apple code is
copied into the reusable numeric model or exported evidence.

Next execute the actual createNewHWPBManager method and connect it to the checked
reset, then integrate matched work, queue/root/event/stamp lifetimes and coherent
readback. Normal reboot is still required before the next live session because
failed warm INIT resources remain retained. Offline investigation can continue.

```sh
python experiments/t6040-gpu/audit-private-pm-allocation.py \
 /boot/GPUC003/private-apple/com.apple.AGXG16X ALLOCATION_RECEIPT.json
python experiments/t6040-gpu/audit-private-pm-creation.py \
 /boot/GPUC003/private-apple/com.apple.AGXG16X CREATION_RECEIPT.json
python experiments/t6040-gpu/audit-private-pm-full-init.py \
 /boot/GPUC003/private-apple/com.apple.AGXG16X COMPLETE_INIT_RECEIPT.json
```

Private implementation-derived research, not a clean-room specification. No GPU
execution, live completion or rendered output proved; no public push performed.
