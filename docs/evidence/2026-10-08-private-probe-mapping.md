# Native probe mapping producers for scheduler kicks and Fender

Private-derived matched AGX353.14 / Apple25G83; offline only. This follows
the CPU PIO mapping audit and resolves the previously missing local producer
of accelerator `358`, the virtual base used by native scheduler kick writes.

The executed setup slice `89a1ce4..89a1edc` obtains two mapping objects from
globals `c6e7938` and `c6e7940`. It calls their virtual address getter at
slot `138`. The first address is stored at accelerator `358` and `f808`;
the second at `f8e8`, the Fender pointer used by native gating methods.
Thus these are virtual addresses, not literal physical addresses to copy into
Linux. Allocation and initialization of the two global mapping objects remain open.

It then calls accelerator virtual `b98` for a relative offset and virtual
`b30` with argument one for a physical base. It truncates the offset to 32 bits,
adds it to the returned physical base and stores the result at region-45
descriptor `c778`. The eight-byte descriptor header comes from constant
`712d7c0`; its values are in the JSON. The second map's virtual `148` getter
supplies the extent, stored as 32 bits at `c978`. The relative offset is
stored at `c980`; `c97c` is zero. The intermediate unused descriptor span
`c780..c977` is explicitly zeroed.

1024 randomized cases execute this native slice with synthetic providers for
addresses, physical base, offset and length. They verify the ordered provider
calls and compare the entire accelerator fixture against exact expected writes.
Vector instructions execute with CPACR enabled; PAC is bypassed. This excludes
earlier flag preconditions and the final virtual `11e8` call after the slice.
It does not prove absolute physical addresses, map lifetimes, actual MMIO
behavior, firmware completion, valid shader preparation or rendering.

Decoded G16X vtable `7eae388` resolves slot `b30` to `89ea17c`,
which loads physical base global `c6e7920` (the leaf ignores the boolean
argument), and slot `b98` to `89e9fa0`, which returns `d00000`.
These leaf targets are inspected, not executed in this randomized checker.
For this G16X implementation the resulting descriptor physical address is
therefore `global[c6e7920] + d00000`; its absolute value remains unproved.
The header constant decodes to flags=2, segment count=1.

Next trace initialization of the physical-base and mapping-object globals,
then compare the resulting regions with the live device tree. Do not
retry the currently retained failed warm INIT without a normal reboot.

```sh
python experiments/t6040-gpu/audit-private-probe-mapping.py \
  /boot/GPUC003/private-apple/com.apple.AGXG16X \
  docs/evidence/2026-10-08-private-probe-mapping.json
```
