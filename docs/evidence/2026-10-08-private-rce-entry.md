# G16 RCE entries, phase backing and descriptor metadata

Matched private AGX353.14 binary. Numeric instruction evidence: 1,024 entry
encodes, 1,024 decodes, 512 phase setups and 512 final metadata patches match native
instructions in emulated RAM. Full destination fixtures preserve unspecified
bytes. No GPU execution, external services or hardware register access.

## Entry format

The G16 encoder vtable slots0/8 bind encodeEntry/getEntry. Each entry is 12 bytes:
a u32 header followed by an unaligned u64 value at+4. Encoding writes:

```text
header = (old & 0xfffc0006) | (register & 0x3fff8) | (flag & 1)
value  = supplied u64
```

Register bits3..17 and flag bit0 are replaced; original bits1..2 and18..31 remain.
Decode returns only register&0x3fff8, flag&1 and value. Thus decode/encode is not
an invertible representation of all header bits. Arbitrary input masks characterize
native behavior, not permission to access arbitrary registers. A zeroed initial
entry yields a canonical header for the tested fields.

append advances the phase byte cursor by12 and entry count by1 after its virtual
encode call. Those counters are u16 fields in the backing at +0x70a/+0x708 relative
to the phase's data pointer. Full append, overrides and the complete register-value
recipe are not executed by this audit.

## Four phase backing areas

Native setup uses phase displacement j*0x720 for j0..3. Actual wrapper tail calls
establish generator inputs as x0 accelerator, x1 command CPU backing and x2
3D descriptor. The nominal mangled symbol contains an extra channel argument;
the actual wrappers do not supply it. Reading the symbol signature literally
would mistake command memory for the channel object.

For each phase, CPU RCE data begins at command+j*0x720+0xa0. GPU RCE address is
`u64(descriptor+0x440) + j*0x720 + 0xa0`, and is saved in command+j*0x720+0x7a0.
The u32 metadata at command+j*0x720+0x7a8 is initially cleared. The encoder object
receives the CPU pointer and its previously initialized vtable. The descriptor
is unchanged during this setup slice.

This ties RCE backing to the same allocation's resource+0x58 mapped output,
while the ordinary 3D payload uses the resource+0x50 mapped output. Their exact
mapping-context/cache-policy roles remain unresolved; do not collapse the two
addresses simply because they refer to the same backing allocation.

## Descriptor finalization

The native final patch writes u64 constant0x0000000400000000 at descriptor+0x820.
Four GPU addresses at +0x828/+0x838/+0x848/+0x858 come from command+0x7a0+j*0x720.
Four u16 counts at +0x830/+0x840/+0x850/+0x860 use command+0x80 for phase0 and
command+0x7a8+j*0x720 for phases1..3. This phase0 exception is directly checked;
do not substitute phase0+0x7a8 merely for symmetry. Other descriptor bytes remain
unchanged. The checked common scheduler encoder consumes these fields later.

## Remaining recipe

These findings provide encoding and backing geometry, not the required register
values for drawing. Full generate3DRegisterListG16Common / write3DRCEBufferSPMPhase
remain to trace, including shader/target/state inputs and variant-dependent data.
Live command size/stride, actual mapping attributes, kick register offsets and
firmware completion remain open. A minimal live job is still unverified.

Reproduce:

```sh
python experiments/t6040-gpu/audit-private-rce-entry.py \
  /boot/GPUC003/private-apple/com.apple.AGXG16X /tmp/rce-entry.json
```
