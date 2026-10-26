# Matched AGX RTBuddy provider and native stop/restart boundary

Offline decoding of the retrieved 25G83 kernelcache closes the missing-provider
artifact gap. It resolves the six AGX delegate slots and supplies the RTBuddy,
AppleA7IOP, and ASCWrapV6 implementation needed to distinguish a normal power
transition from a stopped-CPU restart. It does **not** establish a usable recovery
sequence for the currently wedged GPU: native forced stop retains an idle
precondition, and the preloaded fixup does not copy firmware DATA to its target. The saved GFX
configuration also leaves the separate SRAM backup/restore route unselected.
No GPU, module, MMIO, PMGR, DART, reboot, or APFS operation was performed by this
analysis.

## Identity and reproducibility

Retrieval authorization, read-only mount verification, exact copy identity, and
unmount are bound by
[the retrieval receipt](2026-10-09-matched-kernelcache-retrieval.json).
The local private IM4P `krnl` input is 31,852,893 bytes with SHA-256
`7a9305932f2c7028ec294b55a5ab23844173328eb38639c722a4b54401dcb1eb`.
Its LZFSE payload begins at input offset 58 and is 31,852,507 bytes. The cached
APFS build's `liblzfse.a` and bundled source supplied a local decoder; no package
or network download was needed. The decoded 119,308,288-byte Mach-O has SHA-256
`6158e1c0d591240808e26ff1da050b2fa0ed3eb17c1779d2ddde3171b959536f`,
MH_FILESET type 12, 366 entries, and UUID
`41811D69-3027-674E-E0DB-2F6F64C70EEB`, independently verified by root.

The decoder/indexer is retained privately at
`out/private-apple/decode-matched-kernelcache.py`. It verifies both whole-container
hashes, parses bounded DER/load commands/nlist records, and produces selected
sparse Mach-O views. The views preserve absolute fileset offsets and shared
LINKEDIT; they are not independent `ipsw extract` outputs. Their whole-file hashes
must not be compared with independently extracted kext hashes.

The adjacent JSON contains source hashes, file offsets, calibrated pointer
records, exact review ranges and their hashes, and reduced findings. It contains
no raw disassembly or firmware bytes. Private binary, index, disassembly and
scripts remain ignored under `out/private-apple`.

The matched container's AGX `__TEXT_EXEC` 895,948-byte range is byte-identical to
`/boot/GPUC003/private-apple/com.apple.AGXG16X`, range SHA
`664199816405894110f051eb8a19088991b4ec6e6369b4245df378b3cb0def3a`.
Its 127,784-byte `__DATA_CONST` range is also identical, range SHA
`fa78acc09b6c4140a09fb8fc830b9744779c511d5a642fe40d37f530e7ff39c5`.
The independently extracted AGX file SHA remains
`3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e`.

## Provider and delegated calls

`com.apple.AGXFirmwareKextG16XRTBuddy` is fileset entry at VA
`0xfffffe0007128000`, file offset 1,196,032, bundle version 1. It contains both
`AGXFirmwareKextG16RTBuddy` and the implementation of its
`AGXFirmwareKextRTBuddy` base. Its personality matches `RTBuddyService` with
`role=GFX`. `com.apple.AGXFirmwareKextRTBuddy64`, version 353.14, is a separate
firmware-data dependency with 72 bytes of code, not the missing base-method
implementation. Native RTBuddy is version 1.0.0; ASCWrapV6 is version 1.0.2.

The G16 vtable starts at `0xfffffe0007ea0150`; its constructed address point is
`0xfffffe0007ea0160`. For these matched authenticated function-pointer tables,
`0xfffffe0007004000 + low32(encoded)` resolves the targets, calibrated against
G16/ASCv6 destructor symbols and constructor-selected address points. This is a
bounded observation for this container, not a general pointer-authentication
rule.

| Slot | Resolved target | Method |
| --- | --- | --- |
| `0x880` | `0xfffffe000895a01c` | `setAccelAndFWPointers` |
| `0x888` | `0xfffffe0008959544` | `bootFirmware` |
| `0x898` | `0xfffffe00089593e4` | `sendMessageToFirmware` |
| `0x8a8` | `0xfffffe00089591fc` | `sendAsyncNoteToFirmware` |
| `0x8c0` | `0xfffffe0008958f48` | `changePowerStateTo` |
| `0x8d0` | `0xfffffe00089584a0` | G16 `requestFirmwareBinary` |

`changePowerStateTo` obtains the endpoint's slave processor through
`RTBuddyEndpoint::getSlaveProcessor` at `0xfffffe000b1e7a60` and calls its
virtual `0x818`, resolved to `RTBuddy::setPowerState` at
`0xfffffe000b1de018`. The wrapper is not a direct hardware-reset implementation.
`bootFirmware` consults `RTBuddyService::iBootLoaded` at
`0xfffffe000b1eb6dc`; the non-preloaded path delegates to
`RTBuddyService::loadFirmware` at `0xfffffe000b1eb554`.

The full kernel symbols also resolve AGX's prior opaque external calls:
`0xfffffe000bf26268` is `IORecursiveLockAlloc`,
`0xfffffe000bf2635c` is `IORecursiveLockLock`, and
`0xfffffe000bf2645c` is `IORecursiveLockUnlock`. Therefore
`AGXArmFirmware::stopFirmware` at `0xfffffe00089ca784` clears host flags under a
recursive lock; it is not evidence of a CPU, PMGR, or engine reset.
`AGXArmFirmware::resetFirmwareForRecovery` at `0xfffffe00089d1650` remains a
no-op in this exact driver.

## Native normal power transition

The state-name table at `0xfffffe0007bfe2a8` and management request table at
`0xfffffe0007bfe338` establish the following ordinals and wire values.

| Ordinal | Native name | Management request |
| --- | --- | --- |
|0|SLEEP|`0x0060000000000201`|
|1|ON|`0x0060000000000220`|
|2|PWRGATE|`0x0060000000000202`|
|3|OFF|`0x0060000000000000`|

The remaining names are SLPNOMEM and INVALID. States 0..2 preserve memory in
`RTBuddyEndpoint::powerStatePreservesMemory` at `0xfffffe000b1e8170`.
Ordinary PWRGATE 2 uses the native stopCPU path after its management handshake,
with the second stop argument conditional on hibernation; ordinary nonhibernate
uses0 and turns off the device domain. It is not the SLEEP 201 exchange used in
previous local trials. Native PWRGATE 2 then ON provides an additional contract
to implement offline, not a reason to repeat a failed wake trial now.

The quiesced wake helper at `0xfffffe000b1f33e8` submits 220, or the conditional
alternate `0x00b0000000000020`. A 220 exchange alone is a resume primitive only
when the retained native IOP status selects that route.

## Forced stop and its limits

`RTBuddyService::forcePowerOff` at `0xfffffe000b1eb348` forwards to
`RTBuddy::forcePowerOff(bool)` at `0xfffffe000b1e1a84`. Both boolean routes set
host power ordinal 3, set IOP status 1, disable mailbox interrupts, resize the
endpoint list to 0, release the binary-log handler, and, unless route-only, call
backend `stopCPU(true)`. They then call `enableSRAM(false)` and clear the host
fixup-done byte at offset 0x10b. This top-level method bypasses a management ACK
exchange; `onPanic` alone does not perform this shutdown.

The actual backend's matching is independently qualified by
[the saved-ADT reset review](2026-10-09-rtbuddy-reset-review.md):
`gfx-asc` matches generic AppleASCWrapV6 and the nub matches RTBuddy, rather than
SISP or SEP subclasses. The V6 address point is `0xfffffe0007ec5e88`.
Its `stopCPU(bool)` slot 0x8c0 resolves to `0xfffffe0008a40400`, which passes a
second argument 0 into common `stopCPU(bool,bool)` at
`0xfffffe0008a43270`.

Common stop requires a started backend. If flag 0x132 is set, it tests hardware
idle initially and after up to ten one-millisecond sleeps. Generic AppleA7IOP
initializes strict-idle flag 0x109 to 1; generic V6 does not override it in the
reviewed path. Failure to become idle reaches a panic before CPU-stop writes.
The first forced-stop boolean does not bypass this precondition. Thus bypassing
firmware ACK is not equivalent to forcibly clearing a nonidle wedge. Saved
status 0x6c has neither low idle bit and fails the V6 predicate.

V6 `_isIdle` at `0xfffffe0008a3fc54` tests `(STATUS48 & 3) != 0`, accepting
either low bit. A separate object flag can require CONTROL40 bit 0 first.
It does not require both low status bits. After idle, V6 `_runCPU(false)` at
`0xfffffe0008a3fcf4` reads CONTROL44 freshly, clears 0x10 and writes, then reads
again, clears 0x20 and writes. `_runCPU(true)` reads freshly and sets 0x10 only.
The former local helper omitted the second stop RMW. Saved controls 0 and 0x10
provide no causal evidence that clearing0x20 will change the failed trial;
it may already be zero. This difference alone does not justify a new trial.

After stopping, native common stop invokes `_unmapFirmware`, conditionally
marks the IOP mapper inactive, turns off the device domain for second argument 0,
and clears started flag 0x108. The V6 unmap releases its optional mapping
object at 0x198; it is not a proof that all AGX DMA mappings retire.
`_setMapperActive` at `0xfffffe0008a43bd0` delegates to the mapper's
`setActive` platform function. `_enablePower` at `0xfffffe0008a42d88` calls
AppleARMIODevice `enableDeviceClock` and `enableDevicePower`. The reviewed
native path contains no explicit PMGR RESET31 pulse. The exact internal PMGR
and DART operations and their whole-GPU scope remain unqualified.

## Stopped restart versus quiesced resume

Native ON handling at `0xfffffe000b1e0700..0xfffffe000b1e080c` runs firmware fixup
if needed, records prior IOP status, sets status 4, and calls
`AppleA7IOP::startCPUWithOptions` at `0xfffffe0008a42f40`.
Prior status 1 (forced off) or2 (PWRGATE) selects options 0; prior status 3
(quiesced) selects options bit 0=1. The `running` property at host 0x2231 adds
options bit 1, producing 2 or 3 respectively. The saved ADT applicability review
should decide whether this property is present before an implementation chooses
an option.

With options bit 0 clear, native start enables device power via slot 0x988
(`_enablePowerLate`, `0xfffffe0008a42e84`, then `enablePower`), conditionally
activates the mapper, maps firmware, marks started, initializes mailbox
interrupt/outbox state, conditionally synchronizes IOP timebase, and calls
`_runCPU(true)`. With bit 0 set it skips power enable, firmware map, and CPU-run
writes; the RTBuddy quiesced route subsequently sends the wake management
message. Normal PWRGATE does stop the CPU unless a special running/route-only
configuration selects another path. It is not a universal keep-CPU-running
resume contract.

The preloaded/no-firmware-service contract is explicit:
`pre-loaded` at `0xfffffe0007bf8ccb` sets host 0x2230; `running` at
`0xfffffe0007bf8cd6` sets 0x2231; `no-firmware-service` at
`0xfffffe0007bf8cde` contributes to 0x2232. `_attemptFirmwareLoad` at
`0xfffffe000b1dcf30` uses 0x2232 to skip firmware-service matching, and when
0x2230 is set it calls `_handlePreloadFirmware` directly. `reloadFirmware`
at `0xfffffe000b1e4808` checks a separate generic disable byte 0xd0, requests
native OFF3, then chooses the preloaded route by 0x2230. The no-firmware-service
property does **not** establish that reloadFirmware is unsupported. This
reload route still begins with a native power transition; it is not demonstrated
to recover a dead/nonidle firmware instance.

`_handlePreloadFirmware` at `0xfffffe000b1dd4c0` reconstructs an RTBuddyFirmware
object from retained segment metadata. `preloadedFirmware` at
`0xfffffe000b1ee974` sets its iBootLoaded byte 0xc0 to 1 after
`initWithSegmentMap`. Firmware fixup at `0xfffffe000b1efad4` calls powerOn and
patchbay callbacks, but explicitly skips `copyToTarget` for iBootLoaded firmware.
A forced off clearing fixup-done causes fixup to run again, not a full DATA copy.

V6 `_mapFirmware` at `0xfffffe0008a3fa70` skips mapping for options bit 1; otherwise
iBoot firmware uses `_dartMapiBootFirmware` at
`0xfffffe0008a43584..0xfffffe0008a439d8`. When its retained mapped flag 0x130 is clear, this reads retained 32-byte records:
physical address+0x0, IOVA+0x10, size+0x18, flags+0x1c. It skips records with
flags bit 1, obtains mapper limits via `retrieveVMLimits`, allocates/maps existing
physical records, and sets the mapped flag at 0x130. If the mapped flag is already set it returns without rebuilding those maps.
It performs no DATA byte
copy in the reviewed body. V6 `_unmapFirmware` does not itself clear that iBoot
mapped flag; its broader lifetime must be checked before reconstructing maps.
The reviewed stop/start/map paths also do not write an ASC reset vector.
SRAM calls are conditional/platform-dependent; the independent review found no
`sram-index` for saved gfx-asc, so the generic SRAM wrapper returns unsupported
rather than establishing a real SRAM reset. There is a separate conditional
SRAM backup/restore route controlled by host 0x2244: normal descending PWRGATE
saves selected segments after stop, and ON restores them before fixup/start.
Force-off skips the save. The review resolves `needsBackup` to ADT record bit 2;
saved TEXT flags1 and DATA flags0 both lack that bit. `should-control-sram` is
published by the native AppleA7IOP initialization only with a present
`sram-index`, which saved gfx-asc lacks. Consequently this separate restore
route is unselected for the saved GFX configuration. The generic native driver
has such a route; the preloaded fixup skip must not be generalized to every
RTBuddy personality.

Further offline platform-power/DART and iBoot mapping-lifetime analysis is
useful for a complete recovery contract. It does not prevent the separately
user-authorized experimental GFX RESET31 scope trial through a reviewed,
driver-owned API while all backing is retained. Such a pulse need not establish
whole-GPU retirement in advance; it must not permit backing release afterward
without independent retirement proof. The API, full newly built kernel, and
resident backing owner must be concrete and reviewed before the next requested
reboot. Native idle panic and a potentially ineffective extra 0x20 clear give
no reason to repeat an unchanged wake trial. No result here establishes working
recovery, fresh firmware DATA, or whole-GPU DMA retirement.
