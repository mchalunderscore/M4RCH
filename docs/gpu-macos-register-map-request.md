# T6040 physical-register mapping request

Linux native initialization has consumed the root/object graph and GFenderCfg.
Bumper slot33 and DFenderMGPUCfg slot35 are now concrete required consumers.
The standalone25G83 ABI document and current Gravity platform serializer do
not provide their physical addresses. A speculative host MMIO bank scan hung
the whole machine; exact trigger not preserved. It is quarantined.

## Highest-value return data

For this J614s16-core T6040 and25G83 GPU firmware, establish:

| Slot | Firmware name | Verified consumer | Missing information |
|---|---|---|---|
|33|FenderRegsBumper|read+a0/+a4; write+a0/+a4/+a8 and+88|physical base, extent, read/write attributes, initialization prerequisites|
|35|FenderRegsDFenderMGPUCfg|native attempted write0 to+1704; static read/write+1780 and others|physical base, extent, per-cluster stride/instances, prerequisites|

Prefer the complete set of records referenced by the46-name firmware copy
table, to avoid another handoff for each bank. Names/slots are listed in
`docs/evidence/2026-10-07-gravity-gpu-register-contract.json`; candidate access
consumers in `2026-10-07-gravity-gpu-register-consumers.json`. The inventory is
locally resolved straight-line analysis, not complete coverage. It identifies
210 accesses across12 slots and does not prove bank addresses.

Record source evidence for each mapping: driver binary/build UUID and relevant
constructor/resource-binding instructions, or captured initialization record
with its address space and ownership. Capture physical base, virtual base,
extent/stride, flags and instance count separately. IORegistry resource spans
alone do not identify sub-bank roles. If actual host-created firmware hardware
records can be captured, the register array is hardware+640 with28-byte record
stride; parser copies the first24 bytes only and skips physical0. Specify which
fields represent physical versus firmware virtual addresses. A static GPU HAL
mapping extraction is useful when live record capture is unavailable. Include
power/reset/clock sequence evidence for each bank, not only containment.

## Proven mask behavior

Captured instructions395f4..39624 read hardware+2560/+2568 and conditionally
write Bumper+a0/+a4/+a8. Consumer2a774..2a7c4 reads+a0/+a4, combines64bits,
and partitions ten-bit cluster fields without shifting each result to bitzero.
The earlier cold candidate zeros therefore do not reject its physical identity.
MacOS captured core masks are3db/3db; packed valuef6fdb. Offline producer/
consumer cases pass for16-core,20-core,single-cluster andzero inputs.

Native diagnostic slot33 was substituted with an owned read-only RAM page,
preloadedf6fdb. Firmware produced fullf6fdb, cluster0=3db, cluster1=f6c00,
then faulted on null slot35 write+1704. This establishes sequence/layout behavior
only; neither a native Bumper address nor GPU mask programming is validated.
Hardware+2560/+2568 stayedzero to skip programming. The descriptor physical PA
was patched by the helper to owned RAM; its changes are not firmware writes.

## Current recovery/boot state

Same7.1.13-m4rch-gpu-contract kernel/default, original boot.bin, continuous WFI.
Latest native graph is pinned until normal reboot; never force-unload/free it.
Current boot54817cb4-dc3e-46a6-99c3-432ea842b99e. User reports all peripherals
normal after diagnostic. No kernel package, bootloader or display change needed
for this request. Scanner source/module remain disabled. Keep measured evidence
and proposed mappings distinct in the returned handover.
