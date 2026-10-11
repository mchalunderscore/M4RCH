# Native shared ownership v7

`g16_t6040_shared_v7.rs` supplies one coherent typed ownership component for
the native bundle, support pool, Root pointers, Region A, channels and receive
validators. It composes the frozen v5 range9 bundle geometry without changing
v5, frozen normal v6, or the selected v23 experiment. This is offline work;
there has been no module installation or GPU action.

`NativeTopology::new(bundle_base, support_base, root, region_a, region_c)` takes
owned firmware VAs, verifies 16 KiB alignment, overflow and disjoint allocation
extents, and returns one selected topology. Bundle backing is0x24000; support
backing is0xc4000. Root, Region A and Region C each need0x4000 backing. Address
placement is Linux allocator policy, not an Apple physical-address constant.
The caller still owns page-table permissions and lifetime.

The new RAM execution of the actual matched AGX descriptor and alignment loops
recovers27 support children in range8, logical extent0xc3188 and page-rounded
extent0xc4000. `SupportLayout::address_for_mapping` resolves the native mapping
owner fields; the table preserves the matching CPU owners and exact lengths.
This pool contains statusB (CPU960/map970,0xe440), extra0
(CPU968/map978,0x6a8), statusA (CPU888/map890,0x20), all work/control state,
receive states/rings, the external shared trace data and both small extras.

`channels()` returns17 copyable four-pointer records. Channels0..11 are
priority-major TA/3D/CL, backed by the correct native0x1800 rings. Their three
cursors are allocated RAM addresses at state+0/+0x10/+0x20. Control12 has the
same cursor layout in support+0x300, and its0x4000 ring is bundle+0x1e5c0
(256 records of0x40). No SGX+d60000/d64000 physical aliases are used.

Receive channels13/14 are composite records, so callers must use `rx(kind)`
instead of interpreting all three `state` array entries as cursors. Event uses
support+0xee80 and ring+0xf100, 256 records of0x48; trace uses+0xf080 and
ring+0xb5900,512 records of0x48. Auxiliary uses+0xf0c0/+0xbe900 with256.
Native receive consumer is state+0 and producer state+0x20. The nine log
validators use consecutive0x30 state objects at+0xeec0 and consecutive0x4800
rings at+0x13900. Main200 points to support+0x3c100; its remaining bytes and
Main220 are untouched by the component.

`write_bundle_component` writes the selected native channel and shared-pointer
fields, then reproduces the native shared/header zero initialization and the
two shared1 sentinels. It must run before dynamic hardware/power/time writers.
Header is native child8 at bundle+0xc040, Main+0x10; a timestamp pointer at
header+0x28 has not been source-bound and is not supplied. Native Main+0x471
is the unaligned power pointer. `write_support_component` copies an explicit
initial status into statusA+0 from native FW94c, sets the native+4 flag,
and writes the reached statusB/extra0 fields. FW94c changes with native power
policy; hardcoded3 is not a recovered native initializer.

`root_pointers()` binds Root8/18/20/a8/b0/b8/c0 to these owned objects.
`RootPointers::encode(&[u8;104])` preserves the exact UAT payload the native
Root producer copies from accelerator18d08, object+0x18. The copy itself was
executed and matches compiled Rust, but the upstream UAT payload constructor
remains unbound. Native Root word28 is0x100000000. No donor descriptor is
silently reconstructed inside this serializer.

The selected G16X accelerator vtable address point0x7eae398, slot+a88,
entry0x7eaee20 decodes to89ea1c4. Its actual leaf is a no-op. Complete native
`prepareFirmwareForBoot` was executed in RAM with explicit owned-resource
services: it resets FW1710, calls that selected leaf with true, clears the
first20 bytes of the24-byte Region A terminator, advances the cursor to24,
and preserves the four padding bytes. `write_region_a_component` matches it.
The selected callback does not append a hidden register-init stream.

`NotificationPointers` composes the saved512-case native notify publication
proof. It binds statusB+0x48e0/48e8 to separately owned state/entries resources,
clears statusB48f0(u64),4900/4910(u32), and clears state0/10(u32). It preserves
other bytes. The donor offsets4f88/4f90/4fd4 are not this native object.

AON PTD is a separate one-child range9 allocation: outer CPUc20/mapc28;
child CPUc38/mapc30, logical0xe4, backing0x4000. Actual descriptor and native
alignment execution prove the geometry. `AonPtdLayout` exposes its independently
owned VA. Native ARM power+0x6318 references that VA. Support child26 is an
additional8-byte object at support+0xc3180, map3a8; native power+0x3b50
references it. The power component must bind both from the same allocation
owners; neither is a donor hardware alias.

New qualification compares compiled Rust against the actual matched native
channel/getter/shared-pointer and status producers:1216 Main bytes,802816
support bytes,17 channel records and three RX validators agree. It also
compares the complete native Region A preparation and the actual Root UAT
copy, tests six rejected short/unaligned/overflow/overlap cases without writes,
and checks preserved padding. The native mapping/resource-address services
are explicit RAM fixtures and PAC operations are bypassed; no native allocator,
Linux permissions or hardware behavior is claimed.

Reports are `out/gpu-gravity-normal-boot-v7-shared-source-evidence/source-v6.json`
and `out/gpu-gravity-native-shared-v7-qualification-v3/qualification.json`.
Tracked numeric evidence is under `docs/evidence/2026-10-11-gravity-native-t6040-shared-v7*`.
`SHARED_COMPLETE` remains false until the UAT constructor, remaining dynamic
Main fields, live transport synchronization, mapping policy, and firmware
acknowledgement/execution are qualified by the production integration.
