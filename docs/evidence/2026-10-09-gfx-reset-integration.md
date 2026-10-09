# Reset-kernel integration and first native trial

The user booted `7.1.13-m4rch-gpu-reset` on boot
`ce6572c9-2491-4c87-8e27-6e82cc0ac657`. The live kernel notes match the
qualified checked-reset Image. The prior boot's retained owner ended at the
user's reboot; it was not unloaded or freed by the agent.

Two integration gaps were resolved before GPU publication:

* The new source build omitted a separately promoted USB fixed-host role-provider
  correction. One normal PD probe per device did not resolve that dependency.
  A normal replacement with the existing, ABI-matched correction restored all
  three PD bindings and role providers without rebooting. The corrected module
  and initramfs are now installed with hash-checked backups; Image and GRUB
  default4 are unchanged. A future boot with that corrected archive is untested.
* Candidate v1 rejected the runner's mandatory allocation-only `run_gate=1`
  shadow before allocation or firmware publication. It also inherited a receipt
  flag that would have requested automatic shutdown at gate2. The new actual-C
  admission helper permits clean gate1/nonresident and gate2/resident startup,
  and rejects lifecycle flags before allocation. The preparer explicitly disables
  automatic shutdown; the runner validates the feature contract and graph mode
  before native capture. It now records shadow results durably.

The failed v1 candidate and capture remain unchanged under
`out/gfx-reset-scope/candidate`. A distinct candidate-v2 was built from the frozen
baseline, preserving graph and triangle backing. All eight helpers match the
reset-kernel ABI; its receipt binds ten artifacts and fifteen owner sources.

Candidate-v2 owner SHA256:
`3e71649951e7851490bf6c18e79eddaedba314dd772387c75cc93ba433b51ea4`.
Build-receipt SHA256:
`522a73bd6770532cf1c0213aa485a915b4d961dc0cedbd0e1db87bc552394572`.

The actual startup admission replay passed 80 feature-on and 80 feature-off
prefix cases under ASan/UBSan, plus 16 feature configurations. Userspace replay
passed 40 startup/admission/persistence/copy cases; independent main-path review
passed 16 cases, including refusal before native calls. These do not establish
hardware reset coverage.

## Native result

The new owner's shadow and retained load both succeeded. Firmware consumed all
32 initial controls, then the known recovery handshake stopped at phase2. The
reset experiment used that retained no-work failure state: no triangle or other
GPU work was published. A read-only snapshot showed an active GFX domain at
`0x1f0003ff`, with reset/disable/busy bits clear.

The sole `gfx-reset` command returned `-ETIMEDOUT`. AUTO28 cleared, but the
DEV_DISABLE10 readback did not assert: both the inhibited and disabled samples
were `0x0f0003ff`. The core branched to cleanup before attempting RESET31-set or
the pulse delay. Cleanup returned zero and restored `0x1f0003ff`. This is a
failed device-disable write/readback prerequisite, not a tested reset pulse or
proof that the reset wire cannot work.

Read-only observation followed, then the qualified packet-free stop cleared ASC
START once. Final control44 is zero, status48 is `0x4e`, and all 174 pages,
context, mappings, PM reference and module pin remain retained. The command gate
is permanently sealed. No wake, second reset, new graph, work submission,
unmapping or unload is permitted on this instance.

The independent live review records the precise captures and interpretations:
`2026-10-09-gfx-reset-scope-live-review.md/.json`. USB restoration and persistence
are documented separately in `2026-10-09-gfx-reset-usb-live-persistence.md/.json`.

## Process correction

Future kernel qualification must account for promoted external modules and
initramfs members as well as maintained source fingerprints. A preserved source
hash did not preserve the previously promoted USB behavior. Startup tests must
exercise the actual orchestrator's shadow and live parameter combinations; the
owner command tests alone missed admission that made the candidate unrunnable.

The first hardware outcome also bounds the synthetic register model: tests that
make every written control bit latch cannot qualify actual PMGR bit behavior.
A revised reset hypothesis must be grounded in the matched native sequence and
state explicitly which writes, readbacks and physical completion predicates are
observed. Preserve the old failed capture, retain backing, and use a separately
qualified new candidate rather than weakening the current sealed gate.

The matched native sequence is the next concrete hypothesis. It preserves
DEV_DISABLE10 in an explicit combined RESET31 assertion write and uses
conditional BUSY/delay completion rather than requiring bit10 to read set.
The saved GFX descriptor selects the combined-clear branch; deleting one poll
while retaining fresh read-modify-write assertion would lose that distinction.
See `2026-10-09-gfx-reset-native-disable-semantics.md/.json`. No revised API,
kernel or owner was built or run for this hypothesis in the current trial.
