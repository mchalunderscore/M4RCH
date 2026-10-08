# warm GPU restart: private AGX lifecycle audit

The exact low-level failure is not established. The matched driver shows that
our START + RTKit IOP INIT sequence has not reproduced Apple's provider-managed
boot/power lifecycle. It also exposes a separate GPU recovery handshake. Neither
observation proves that a particular missing register write caused status0x48.
No additional hardware trial was run for this audit.

## native failure being explained

On boot fa78dd48-b214-46fc-8786-cae63897ad78, cold initialization, 32 consumed
opcode16 controls, acknowledged AP quiesce/IOP sleep, verified ASC stop0/6e,
owned mappings removal and normal unload succeeded. All71 owned allocations
were retired. The subsequent warm START + INIT0x220 produced no mailbox messages,
HELLO or endpoint map in four seconds. Final control0/status48 failed our stop
check. No new warm graph was allocated or published. The failed probe remains
pinned; clear it with a normal reboot, do not force-remove it.

The Oct7 explicit-wake and managed-wake captures already reproduce this failure,
including an attempt with START unchanged and GFX power continuously held.
Therefore neither START toggling nor a GFX power release alone explains it.
Cold resource retirement and successful firmware restart remain separate results.

## artifact and reproducibility

Private `/boot/GPUC003/private-apple/com.apple.AGXG16X`, AGX353.14 from Apple25G83,
SHA256 `3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e`.
The local disassembly and symbol index remain ignored under `out/private-apple`.
This is implementation-derived analysis, not clean-room. No binary, firmware TEXT
or complete disassembly belongs in the return bundle.

Run `experiments/t6040-gpu/audit-private-wake-lifecycle.py <private-macho> <json>`.
The saved JSON checks43 instruction sites and8 ASC vtable targets. Static words
pin the reviewed sites; they do not independently prove semantics or causality.
The constructor at89d30c4..89d30dc fixes the ASC vtable address point at
fffffe0007ea8668+10. Image-specific encoded pointer targets use base
fffffe0007004000 plus low32 bits, calibrated against both named ASC destructors;
this decoding is not a general pointer/PAC rule for other images.
All shortened code addresses below retain prefix fffffe000.

## what the driver establishes

1. **Boot is delegated.** `initWithPayload` (89ca438) installs an IOService pointer
   at host1668+role*38 and calls its virtual slot880. `bootFirmware` (89ca7cc)
   clears host1690/1715, calls that payload's slot888 with the object at host1688,
   checks the return value, then waits for host1715. This wrapper does not reveal
   the provider's hardware boot/reset sequence. `notifyFirmwareStarted`
   (89b7948) sets1715 and wakes the waiter, then sends the mapped root using the
   payload's slot898 and packet class81. The callback and root publication are
   distinct steps, not proof that our earlier cold control consumption completed
   every Apple host initialization step.

2. **Power changes also use the provider.** `changePowerStateTo` (89c89e4) forwards
   its requested state through payload slot8c0. `isFWAwake` (89c7e9c) tests bit0
   of payload byte189, inverted. It does not decode ASC status0x48.
   `waitForFirmwarePowerOff` (89bf120) polls shared power-object+10;
   `snapshotASCPowerGeneration` (89bf1b0) saves shared+1c;
   `waitForNextASCPowerGeneration` (89bf160) waits for that generation to advance.
   Direct ASC control/status access is not the full host lifecycle contract.

3. **The candidate reset helper is empty.** `resetFirmwareForRecovery`
   (89d1650) consists of a branch-target hint and return. There are no hidden
   reset register writes in that particular function. `stopFirmware` (89ca784)
   clears host1714 between external calls on host16e0. Those external functions
   are not file-backed here; do not mislabel them as ASC reset/power-off APIs.

4. **GPU recovery is not RTKit management sleep.** In the conditional inspection
   path of `stopFirmwareForRecoveryInspection` (89ca56c), Apple sends
   `0x0086000000000000 | (accelerator+688 token & ((1<<44)-1))` through payload
   slot8a8 with argument1. It waits for self slot1d8, resolved to
   `getNumDeviceRecoveries` (89ca40c), to equal token+1. That getter reads a u64
   at shared-status+48f0. It then requires self slot1e0, resolved to
   `isFirmwareStoppedForHostRecovery` (89ca3ec), which tests u32
   shared-status+4910 !=0. The polling path drains firmware rings and checks
   `isSystemSleepNotificationInProgress` (self slot700,89d15d0), which reads
   the separate shared power-object+8 flag. These are application-level recovery
   predicates. They are not the ACK or status predicates used by our RTKit sleep
   test, and this audit does not justify sending86 to the current failed probe.

5. **Additional recovery state lives in shared memory.** Self slots480/488 resolve
   to pre/post-recovery predicates (89c27e8/89c27c8), testing shared-status+4900
   against1/3. The corresponding resume helpers (89c28b8/89c2828) check those
   predicates and update4900 to2/0 with barriers. This does not supply the
   provider's ASC wake, reset-vector, firmware DATA or page-table restoration.

6. **The likely provider is identifiable, but its implementation is absent.**
   `AGXAcceleratorG16::start` (89d9f58; references89d9f80..89d9f90) installs the
   selector strings `AGXFirmwareKextG16RTBuddy` and
   `AGXFirmwareKextRTBuddy - AGXFirmwareKextG16RTBuddy` at accelerator1af60.
   `requestFirmwareBinary` (89d80d4) delegates to its service argument's slot8d0.
   These are concrete provider-selection/delegation evidence. The runtime IOService
   instance and its inherited method implementations must still be resolved;
   this AGX extraction contains no AGXFirmwareKextG16RTBuddy implementation.

## interpretation and next evidence request

**Established:** no-message warm restart after an acknowledged sleep and verified
cold unload; Apple AGX delegates boot and power to a payload provider; the named
reset helper is a no-op; separate GPU recovery state/protocol exists.

**Working hypothesis:** sleep ACKs plus START/INIT are insufficient to reconstruct
that provider-managed lifecycle after our shutdown. Provider power transition,
reset-vector handling, firmware state restoration or a different resume protocol
may be missing. The binary does not select among these explanations.

**Unknown:** exact meaning of0x48, whether the firmware executed after warm START,
whether the boot vector/DATA/tables need restoration, and whether cold recreation
or in-place resume is the supported native sequence. Do not invent reset bits or
claim that a longer wait will fix it.

For the macOS agent: from the same Apple25G83 kernelcache (UUID
41811D69-3027-674E-E0DB-2F6F64C70EEB), identify and privately extract the service
implementing `AGXFirmwareKextG16RTBuddy` and its RTBuddy base/dependencies. Keep
all proprietary binaries private. Return hashes, bundle IDs, versions and symbol
indexes; preserve kernelcache base/chained-pointer context. Resolve provider
virtual slots880/888/898/8a8/8c0/8d0 and inherited targets, including boot
versus resume selection, management-message ordering, power transitions,
ASC control/status expectations, reset vector and DATA/table preservation.
Resolve AGX external sites bf26268/bf2635c/bf2645c using the matched kernelcache
symbol map rather than guessing their names. If available, include read-only
IORegistry evidence linking the provider to this G16S GPU. A normal native
idle/wake trace is useful only if it can be captured without destabilizing macOS;
no blind writes or hardware reset experiments are requested.

We can continue offline Linux ABI work and future cold batches. A normal Linux
reboot clears the retained failed probe. A macOS visit is needed only to obtain
the missing matched provider artifact/runtime evidence, not to recover Linux.
