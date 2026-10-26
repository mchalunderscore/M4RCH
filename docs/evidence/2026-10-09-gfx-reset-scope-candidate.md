# Checked GFX reset scope candidate

A distinct kernel and retained resident owner are built and independently reviewed. This prepares a hardware experiment; it does not establish recovery, teardown, execution or DMA retirement. The old live owner on boot `278a044e-6204-4893-83dd-0ef198566470` remains sealed on `7.1.13-m4rch-gpu-contract`, with all 174 pages retained. The new kernel is now installed additively, with a separate boot entry; it has not been booted or pulsed. See `2026-10-09-gfx-reset-boot-installed.md/.json`.

The matched Apple kernelcache was retrieved from APFS Preboot through a verified read-only mount and then unmounted. Matching AGX bytes and the six RTBuddy delegate slots now resolve against the original 25G83 image. The native PWRGATE/ON lifecycle is useful evidence, but generic ASCWrapV6 forced stop still requires hardware idle. It does not prove recovery from the observed nonidle stall. The extra control44 mask0x20 clear would be a no-op for the saved controls and is not a new wake experiment.

The experimental alternative uses the real GFX PMGR provider at `/soc/power-management@288e80000/power-controller@110`, not the virtual GFX-ASC gate. The reviewed kernel API excludes other reset users, holds the provider/domain locks, requires powered ACTUAL/TARGET15 without busy/reset bits, checks every write/readback and attempts error cleanup. Reset bit31 and DEV_DISABLE bit10 are distinct from PS_RESET bit12. Its successful return would qualify register observations only; engine, ASC, translation/cache and DMA reset coverage remain unknown.

## Frozen identities

| Artifact | Identity |
| --- | --- |
| Candidate | `out/gfx-reset-scope/candidate` |
| Future kernel | `7.1.13-m4rch-gpu-reset` |
| Kernel Image SHA256 | `39f25240a6d4ccfdea340c1c8a88915c22e6997b30d1146e3bbba88868a7cbba` |
| Kernel notes SHA256 | `73827a9260e9c49f49036380e62c14d8f2a535edabb808914af7ecbcec05f013` |
| Kernel build ID | `56bf77789b445b0e35cda49f621ff79122eb8d77` |
| Kernel qualification SHA256 | `47e6e5c9027da74d3b98b4877415f24cd393baf2858c9567d73da2f31e0ec95b` |
| Graph owner module SHA256 | `45ec9be8dded694b3f1c3029cee03018af9061e26500143b9b65371008dc1d6f` |
| Candidate build receipt SHA256 | `a60d3e4d2a0e54ad3f6818480cbe9c021fc7bbffe4eff7c2495c1c34706144ac` |
| Graph SHA256 | `287f2c53bc6ef7ed226c4a2995b9d9904e7623acae9713af105be6b04fc690a9` |
| Backing SHA256 | `35112ef3c261673bda227a3867a0d2b9dd58ac89f35f7bba9c8c05f1dee118d3` |

All eight helper modules were rebuilt W=1 for the future release. Root and independent review checked all 10 declared artifact hashes, all 14 owner-source hashes, both API imports, exact kernel notes and preservation of the graph, backing and joined/receive sources. The separate kernel retains 38 of 39 maintained fingerprints unchanged; only the reviewed PMGR source differs, plus the new public header. Configuration changes only the release suffix. The old kernel and candidate are unchanged.

The preparer initially omitted `boot-contract.h` because its exclusion pattern also matched header files; that failed build is retained under `candidate-build-failed-v1`. The exclusion now applies only to boot capture directories, and the successful candidate contains the original header. A later metadata correction makes the legacy top-level envelope module hash agree with the rebuilt artifact map. No compiled file changed for that correction and the runtime artifact validation was already correct.

## Owner and verification

The explicit `GFX_RESET_SCOPE_TRIAL` feature adds typed `gfx-snapshot` and `gfx-reset`. Reset requires the retained pin/context/mappings/runtime-PM ownership, all 174 pages, no submitted work, all 36 work cursor words zero, all 256 TA records inactive and equal consumed control cursors in bounds. It admits phase0/healthy or phase2/failed and permanently seals before calling the API. A host precondition refusal consumes the gate without claiming API entry. The wrapper records command intent before opening sysfs; an uncertain write cannot authorize a retry.

After the command only sample, GFX snapshot and packet-free stop are available. The reset path sends no wake/INIT/control/work packets, performs no automatic restart, and frees no memory. Stop clears ASC START once, retains diagnostics and backing, and is not proof of hardware quiescence. Receive workers serialize on the same graph mutex and stop publication after sealing.

Verification passed: 98 actual driver C fault cases, 513 actual owner C cases with ASan/UBSan, 88 default-off regression cases, 31 persisted root wrapper/copy checks and 26 independent wrapper checks. API/MMIO/PM/transport and scheduling are stubs in offline replays. Physical reset scope and real kernel concurrency still require the fresh boot experiment. Independent evidence is in `2026-10-09-gfx-reset-api-review`, `gfx-reset-resident-owner`, `gfx-reset-owner-review`, and `gfx-reset-kernel-candidate`.

## Future bounded trial

The future kernel is installed additively. The fifth entry, `7.1.13-m4rch-gpu-reset (GFXR001 checked reset trial)`, is now default4 at the user's request. A normal reboot will select it without GRUB input. The user requested pausing the goal until they report booting it. Do not run this candidate on the old kernel or old retained session. Confirm the new release and notes, a different boot ID, no conflicting GPU module, all three PD bindings and all three USB role providers. The wrappers enforce the exact future image/module identity and reject repeated initial captures.

On that fresh boot, establish the new no-work retained instance once:

```sh
sudo -n python experiments/t6040-gpu/run-root-envelope.py out/gfx-reset-scope/candidate --graph --run
```

Inspect the initial capture before choosing the pulse. If module/PM/backing ownership and the expected eligible state are present, collect the read-only observation:

```sh
sudo -n python experiments/t6040-gpu/run-resident-gpu.py out/gfx-reset-scope/candidate gfx-snapshot
```

Then the single explicit scope experiment is:

```sh
sudo -n python experiments/t6040-gpu/run-resident-gpu.py out/gfx-reset-scope/candidate gfx-reset
```

Do not retry after refusal, error, interruption or success. Compare API valid fields/errors and ASC/protocol/journal evidence before/after. No triangle is submitted in this scope experiment. Do not follow it with warm START/INIT, a new graph, unload, unmap or backing release. Snapshot/sample/stop remain available. Subsequent work must separately establish physical cessation of access, restoration of firmware state and a coherent restart before repeatable teardown can be claimed.
