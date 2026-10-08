# Native SKU microsequence buffer selection and finalization

Matched private AGX353.14 / Apple25G83. Native beginEncoding and finishEncode
execute in emulated RAM. 1,024 selection cases, 1,024 finalization cases,
32 all-unavailable failure cases, and512 ordinary 3D caller/native-finalizer
compositions pass. Full encoder, backing and output bytes are checked. No GPU
hardware touched. Binary/function hashes and numeric examples are in the JSON.

## Buffer selection

AGXSKUEncoder::beginEncoding 0x8a16958..0x8a16ba4 stores its u32 third argument
at encoder78. Encoder8 points to the accelerator. The audit keeps accelerator
byte1aed4 bit3 clear, excluding the optional external logging/locking path.

The initial candidate is `(u32(encoder60+1)) % encoder58`. It starts **after**
the previously selected slot. For each candidate, an external function a7d0308
receives encoder38 and encoder40+candidate*64. Native code tests its return bit0:
1 selects the candidate, 0 advances modulo capacity. Exhausting capacity reaches
an assertion path at8a16b7c. The audit intercepts this before external failure;
it does not infer the provider's availability/retirement semantics.

The vector count at encoder48 supplies bounds independently of capacity58.
Native checked-pointer guards precede accesses. Fixtures use valid low unsigned
pointers and matching counts/capacities1..32; capacity0, pointer-tag/overflow
paths and mismatched-vector failure cases are not qualified by this audit.

On success, encoder60 becomes the selected index. External a7d0d18 receives
encoder38, the event pointer originally supplied in x1, and the selected64-byte
record pointer. This event-association callback is synthetic in the audit.

Encoder50 is the u64 buffer stride; encoder28 is the CPU backing base.
Native stores `base + stride*selected` to encoder68 and the low32 bits of
`stride*selected` to encoder5c. Audits exercise strides64/128/256/512; these
are fixture choices, **not** discovered native defaults or valid maximums.

## Finalization

AGXSKUEncoder::finishEncode 0x8a16ba4..0x8a16cdc appends u32 `0x40000002`
at the current CPU pointer encoder68, then advances that pointer by4.

If the caller supplies a nonnull size-output pointer, it writes:

```
used = u32(low32(new_cursor) - low32(cpu_base) - offset32)
reported_size = u32(used + 63) & 0xffffffc0
```

Here cpu_base=encoder28, offset32=encoder5c. Safe fixtures reduce this to
rounding `(payload_bytes+4)` up to64bytes. The subtraction/addition are actual
u32 arithmetic, not a promise of validity for overflowed/huge buffers.

**The reported size includes alignment padding, but this method does not zero
that padding.** Full backing comparisons prove that only the four-byte terminal
word changes. Buffer initialization/reuse must establish any padding requirements
elsewhere. This is also not proof that arbitrary preceding bytes form an
executable microsequence; the terminator's full protocol meaning is not tested.

After optional size publication, resource pointer encoder20 is called at virtual
slot158. That synthetic mapped result plus encoder5c is supplied to the firmware
mapper at virtual slot2d8 with x2=0. The firmware comes from
`*(encoder8 + 0x5b0)`. Native tail-calls that mapper and returns its result.

The two maps are distinct operations; do not replace the firmware translation
with CPU arithmetic or assume a mapping context/cache policy. The audit supplies
independent resource-map and firmware-translation returns and checks arguments,
including u64 address addition. PAC operations are bypassed for unsigned fixtures.

## Ordinary 3D command publication

Caller 0x89d5980..0x89d5990 reads its SKU encoder from channel+a8 and calls
native finishEncode with size output at command+1c. It stores the returned GPU
address as an **unaligned u64 at command+14**. The composition tests execute
finishEncode itself and both explicit mapping stubs, then compare the entire
command fixture, rather than substituting a fake finalizer.

This connects stream buffer lifetime/size publication to the command headers
checked previously. Stream buffer selection belongs to a separate SKU encoder
pool; it does not establish the ordinary 3D command's allocation stride.

## Remaining integration

Still needed: actual SKU stream instruction construction, native default pool
configuration, external availability/event-provider semantics, map/cache context,
phase0 full model, valid shader/target/parameter storage, live kick and completion.
No live draw is claimed. Failed warm INIT remains retained; normal reboot before
new hardware experiments, no forced unload or blind repeat warm INIT.

Reproduce:

```sh
python experiments/t6040-gpu/audit-private-sku-buffer.py \
 /boot/GPUC003/private-apple/com.apple.AGXG16X /tmp/sku-buffer.json
```
