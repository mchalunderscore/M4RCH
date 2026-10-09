# Recovery dispatch hardware trial — boot 278a044e

The prepared mask3 candidate ran once on fresh boot
`278a044e-6204-4893-83dd-0ef198566470`, kernel
`7.1.13-m4rch-gpu-contract`. Module SHA256:
`332d9d04f3dc2ada1de5b312910a5d5e65eb92165a28f9a6f3768cb627b81191`.
All three PD bindings and USB role providers were present before and after.
No reprobe was needed. Source baseline was `8df046c`.

Recovery remains incomplete: 0 of 2 requested idle cycles completed. Final
counter1/phase2, host-stop1, request0/flag1, controls32/32/32. No work was
submitted. Main module/context/all174 DMA pages remain retained and sealed.
Only typed sample/stop is permitted. Do not repeat this candidate, force
unload, free backing, or use the previously failed START/INIT wake sequences.

The diagnostic expansion yielded useful positive evidence. The healthy journal
contains50,458 records, including42,052 strictly increasing native trace records
and8,406 statistics records. The fresh recovery-role marker is sequence22832,
timestamp3923330416, packed04000046/function0, args(0,0x1000,4,0), after host
prefix22823. Within the qualified native attribution it supports progress past
the first power-worker wait to64c0, not a current PC.

After that marker,3,003 complete main-handler pairs remain visible. The first
triplet clears pending7→5→4→0 with handlers2,1,4, no hold or held pending.
Thus the main scheduler continues dispatching. Periodic producers also emit
these masks, so unique attribution to recovery's mask7 publication is not
established. No bit25 entry or pending argument was observed; phase3 and a fresh
control were absent. This prioritizes normal sampler event8 wake/ACK or an
earlier postmarker boundary, without identifying the blocked firmware PC.

Existing sampler trace bit6 covers a different long path; it cannot directly
observe the normal event8 ACK. Another trial solely adding bit6 would not supply
a decisive normal-ACK observation. See the independent
`2026-10-09-recovery-dispatch-live-review.md/.json` for exact pairs and scope.

The related reset investigation established that the real GFX PMGR provider is
registered and advertises zero reset cells. Its live metadata has no phandle
property, so a legitimate reset consumer reference still needs qualification.
ADT power topology puts virtual GFX-ASC and GFX-SGX gates beneath real GFX386;
reset wiring, cache/translation coverage and DMA quiescence remain unproved.
The generic reset driver's success return alone does not establish its writes
or their effect. See `2026-10-09-pmgr-reset-scope.md/.json`.

Root then ran the W=1-built capability-only helper once at gate1. It confirmed
the registered provider has no usable internal phandle and returned ENODATA
before constructing a private consumer or acquiring a reset reference. No reset,
MMIO, power transition or DT mutation was possible in this helper. It is absent
after the check; the retained main module's size/refcount remain7913472/1.
The helper's private-consumer lifecycle remains unexercised. Its module SHA256
is62d38420f61e370b4c8f84d2287abdc9db528ec9e43dbe1d5268fcaa576f5472.

The joined firmware notification/task/semaphore analysis adds19 actual RAM
cases beyond the earlier short callback stubs. An early normal ACK is retained
until consumed, and notification-before-block avoids a simple lost wake.
Real context switching, runtime queue coherence and live task scheduling remain
outside the check. No new required host graph or MMIO input was identified.

Root independently reran the persisted19-case harness against this boot's saved
TEXT. The numeric results match the agent receipt except for the output path.
The ELF wrapper was rejected on length before emulation; the qualified raw TEXT
was then used. Root receipt:
`out/recovery-dispatch/sampler-kernel-wake-root-278a044e.json`.

The user then identified the missing matching kernelcache in the M4RCH APFS
subvolume and explicitly required a read-only mount. Root retrieved it from the
unencrypted Preboot volume, verified the exact original SHA256
7a9305932f2c7028ec294b55a5ab23844173328eb38639c722a4b54401dcb1eb and unmounted.
The private copy remains ignored under `out/private-apple`. This removes the
artifact-access gap from the earlier mounted-file inventory. See
`2026-10-09-matched-kernelcache-retrieval.md/.json`.

Matched provider analysis and independent review now resolve the six delegate
slots and establish the actual ASCWrapV6/RTBuddy-v2 configuration. Native idle
uses PWRGATE202 rather than SLEEP201. Forced IOP stop still has a strict hardware
idle prerequisite, which saved status6c fails. Its additional control44 mask20
clear is not a causal lead: saved controls were0/10, so that clear would likely
be a no-op. The actual preloaded path supplies no full DATA restoration. See
`2026-10-09-rtbuddy-matched-provider.md/.json` and `rtbuddy-reset-review.md/.json`.
These contracts do not justify repeating the old wake trials.

The driver-owned checked GFX reset API passed a final W=1 object build and98
actual-C fault cases, independently reproduced from the exact patch by reviewer
and root. It remains an experimental device-reset scope hypothesis with all
backing retained. A separate kernel and explicit resident owner are now built and independently
reviewed; nothing has been deployed or pulsed. See
`2026-10-09-gfx-reset-scope-candidate.md/.json` for exact future identities and
the bounded test. Command readback will not
establish whole-GPU reset coverage or authorize memory retirement.

The adjacent receipt binds capture/analyzer/preflight hashes. Its final owned
snapshot has startup count1222; the preceding final host log sampled1201.
Those are separate observation times. No completed recovery, rendering or
joined memory retirement is established. No additional reboot is requested
before a distinct, concrete next candidate is ready.
