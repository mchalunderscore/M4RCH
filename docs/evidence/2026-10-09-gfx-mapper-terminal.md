# Matched GFX mapper terminal and PMGR gate bindings

The native provider path contains no newly qualified GFX mapper isolation or
drain operation. Its last resolved step is a nonwaiting lookup of an IOResources
property named `setActive`. The separate native power gate function is a
disabled-state query, and the firmware stop path's null output makes that query
return without a hardware read or write. The native clock gate function carries
the actual device vote transition. Its saved virtual401 descriptor selects the
real GFX386 state word; it does not expose another physical ASC reset register.
Native AFR policy forces AFR385 to remain ON. For a normal target-zero write,
the conditional native bit11 wait expects that bit **clear**, not set.

This offline review continues the unresolved boundary in
`2026-10-09-gfx-native-poweroff-boundary.json`. It does not repeat a hardware
trial, change an owner or kernel API, modify boot state, or release any mapping.
The adjacent JSON binds the complete matched 25G83 kernelcache, embedded
personality metadata, saved boot `a1f61d61` ADT, 49 exact native byte ranges,
15 vtable words and 11 initialized/name-linked strings. Full native code and
disassembly remain private in ignored `out/private-apple/gfx-mapper-terminal`.

## Mapper call reaches the platform resource registry

The saved mapper phandle437 selects `/device-tree/arm-io/mapper-gfx-asc`, with
compatible `iommu-mapper,gfx`. Its embedded personality selects
`AGXArmFirmwareMapper` over `AppleARMIODevice`. The native device publication
and personality construction path then gives this provider chain:

1. `AGXArmFirmwareMapper` forwards `setActive` to its `AppleARMIODevice`.
2. That nub uses inherited `IOService::callPlatformFunction` to forward to
   `AppleH16GFamilyIO`, selected by saved `arm-io,t6041`.
3. H16 forwards to its `AppleARMIO` superclass, whose platform method resolves
   to the same IOService provider forwarding body.
4. Its `IOPlatformDevice` nub for `arm-io` also inherits that forwarding body.
5. The root `AppleARMPE` personality matches the saved root's `AppleARM`
   compatible. Its inherited `IODTPlatformExpert` path reaches
   `IOPlatformExpert::callPlatformFunction`.

The construction evidence matters: `AppleARMIO::publishBelow` attaches the
created ARM device nubs to itself; `IODTPlatformExpert::processTopLevel` invokes
`createNubs` with itself as the nub provider; and `createNub` instantiates
`IOPlatformDevice`. This qualifies the selected native construction path, not
a live macOS IORegistry snapshot.

The relevant method selectors are now bound to initialized names. The H16
override compares `newAppleARMFunction` and `IOPlatformActiveAction`. The former
is interned by `AppleARMFunction`'s initializer; the latter is interned from its
own exact string and assigned to the global action key. Neither is `setActive`.
`AppleARMPE` handles coprovider lookup/removal, `SecureRoot`, and
`callAppleARMFunction`; its initialized keys and name comparisons do not select
`setActive` either. These are positive selector bindings, not conclusions from
an unsuccessful string search.

`AppleA7IOP::_setMapperActive` supplies the literal `setActive`, the requested
boolean in its first platform parameter, and `wait=false`. At the final
`IOPlatformExpert` entry, that nonwaiting path reads the global constructed
`IOResources` object, calls `copyProperty(setActive)`, and checks whether the
returned object derives from IOService. Only a valid service receives the same
platform call and parameters. No resource, no property, or a nonservice value
leaves `kIOReturnUnsupported` (`0xe00002c7`).

The remaining dynamic binding is precise: the runtime IOResources property
named `setActive`, if present, and that service's actual class. The saved ADT
and kernelcache do not include that live registry object. Consequently this
review resolves the terminal dispatch contract but cannot label the actual
call a no-op, a translation disable, or a drain acknowledgement. A generic
DART implementation is still unrelated to this GFX UAT mapper.

## The provider's clock and power functions are different

The saved `arm-io` ADT contains two eight-byte function descriptors. Both point
to PMGR phandle265 (`0x109`), which resolves to the saved `pmgr1,t6041` node:

| Property | Native tag | Constructed function object | Actual PMGR dispatch |
| --- | --- | --- | --- |
| `function-clock_gate` | `0x636c6b47` | `ApplePMGRFunctionClockGate` | `_enableDevice` |
| `function-power_gate` | `0x70777247` | `ApplePMGRFunctionPowerGate` | `_wasDeviceDisabled` |

`AppleARMFunction::withProvider` reads the descriptor, uses its first word to
match the registered `IOFunctionParent00000109` service, and asks that service
for `newAppleARMFunction`. The matched PMGR factory dispatches the second-word
tags above to the two concrete classes. Both initialize their target as the
matched PMGR object. This resolves the earlier unspecified H16 function
objects without assuming their effect from their names.

For the qualified firmware stop path, `AppleA7IOP::_enablePower(false,0)` calls
provider clock disable at index0, then provider power handling at index0 with
a null output pointer. The ARM device nub translates the index to saved virtual
gate401 (`GFX-ASC`). H16's cached clock function then reaches actual
`AppleT6041PMGR` vtable slot`0x948`, bound to
`ApplePMGR::_enableDevice` at `0xfffffe000984ce74`. Its arguments are device401,
enabled0, secondary flag0 and die0. That command-gated path updates native
per-device votes and propagates through the native parent graph. The actual
selected path is detailed below; its dynamic vote and notification state has
not been observed in a live native object.

H16's power function reaches actual PMGR slot`0x968`, bound to
`ApplePMGR::_wasDeviceDisabled` at `0xfffffe000984e68c`. Its command-gated body
checks the output pointer before inspecting device state. The stop path passes
null, so that branch returns without reading or writing hardware. This is
**not a second physical power-off command** and gives no independent OFF
acknowledgement. The power function wrapper returns zero; the clock wrapper
also returns zero after its device call, and `_enablePower` ignores both
provider statuses before returning zero itself.

## Virtual401 propagates to GFX386; AFR385 stays ON natively

`_enableDeviceGated` converts `(enabled0, secondary0)` to desired state0 and
stores the direct device vote at object `+0x3e7d4 + die*800 + device`.
`_updateDeviceStatus` aggregates votes, compares the resulting state with its
cached aggregate, and recurses through `_getDeviceParentsID` before appending
changed device records. The saved parent chain is GFX-ASC401 → GFX386 → AFR385.
Dropping one vote does not guarantee GFX reaches0 if another native vote remains.

AFR's descriptor flags are `0x09`. `_updateDeviceStatus` explicitly tests bit3
at `0xfffffe000982ff04` and forces desired state15 at
`0xfffffe000982ff2c`. Thus AFR staying ON is consistent with Apple's own policy;
this result supplies no reason to write AFR or bypass its ownership.

GFX-ASC401 and GFX-SGX400 both have flags `0x10`, no physical PS word, and
GFX386 as parent. `_syncDeviceStatusChange` tests bit4 and skips physical
transition handling for these virtual descriptors. Its OFF iteration skips401
and reaches the real GFX word through device386. The already qualified address
translation is native RegMap6, offset `0x110`, physical `0x288e80110`.

The saved401 and386 records have zero performance-domain selector byte `+2`,
post-off selector byte `+0x0d`, cluster/XNU selector byte `+0x0f`, bridge count
byte `+0x18`, and cluster ID byte `+0x19`. Consequently those saved records do
not select a separate ASC cluster gate, post-off action, or bridge teardown.
The higher native API still contains conditional PMP/PMC notification and
runtime lock/cluster structures. This review does not observe those constructed
objects or establish equivalence to Linux genpd, and it does not infer a missing
raw register from that limit.

## Target-zero bit11 predicate is explicit

For desired state0, `_setPSLevel` supplies an ACTUAL wait with mask `0xf0`,
expected `0x00`, budget argument `0x2ee00`, and die0 at
`0xfffffe000982d750..0xfffffe000982d7a0`. That wait alone does not check bit11.

The T6041 write wrapper calls the parent `ApplePMGR::writeReg32`. After the
write, when object `+0xb0` bit0 is set, the actual `isPsReg` recognizes the
address, and the written TARGET differs from15, the parent dispatches another
wait. Its exact arguments at `0xfffffe000983d034..0xfffffe000983d044` are:

| Argument | Value for GFX target0 |
| --- | --- |
| RegMap and offset | 6 and `0x110` |
| Mask | `0x800` |
| Expected value | `0x000` |
| Budget argument | `0x2ee00` |
| Die | 0 |

The actual T6041 wait method at `0xfffffe0009c12024` tail-delegates with unchanged
arguments to parent `ApplePMGR::waitReg32` at `0xfffffe000983d09c`. Its comparison
at `0xfffffe000983d140..0xfffffe000983d148` is
`(read_word & mask) == expected`. It returns immediately on equality; after
the budget expires it performs a final read and may panic according to native
object `+0x16d` bit0. The budget is added to `mach_absolute_time`, so it is not
identified with the Linux owner's time units. Native object `+0xb0` policy has
not been read live.

Therefore the reviewed target0 branch does not expect bit11 to become set as
an inactive acknowledgement. Raw `0x0f000b00` gives `0x800` under that mask and
fails this native clear condition if the conditional wait is enabled. The
frozen owner's stronger OFF predicate and its failed classification remain
unchanged. Register OFF and safe backing retirement remain different claims.

## Effect on the next decision

These bindings support the distinct normal GFX provider power-off observation
already prepared by the owner. They supply no missing second native power
write, no independently selected ASC reset register, and no mapper operation
that can safely be copied into the current
sealed experiment. A valid independent PMGR OFF observation and retained
firmware-owned DRAM samples remain the relevant hardware evidence.

Even OFF plus stable samples would not establish all outstanding fabric
transactions, private cache writeback, every UAT context or every DMA engine.
Keep joined backing, page tables, mappings, consumer and module pinned. Fresh
firmware DATA and a qualified restart protocol remain separate requirements.
This source result does not authorize a warm START/INIT retry, unmapping,
module unload or backing release.
