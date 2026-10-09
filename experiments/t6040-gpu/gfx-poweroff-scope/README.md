# Retained GFX power-off scope

This is a distinct future cold-owner hypothesis using the installed Gravity
kernel's normal runtime-PM path and existing driver-owned GFX snapshot API.
It has no reset command, kernel/API change or hardware result. Keep the current
native-reset owner and its consumed trial unchanged.

## Exact source integration

The source baseline is the frozen
`out/gfx-native-reset-owner/candidate/asc-graph-init` directory:

- `gfx-reset-scope.h` SHA256
  `0da5611ee7601f21a102886a7f0d79c7259fd11d471a456bed23d830b3638147`.
- `recovery-cycle.h` SHA256
  `94a52c7d5901eecc26b512f21e2f82f5c72099051f4cd814b8b7cf44c1518f09`.

In a separately prepared candidate, copy this kit's `gfx-poweroff-scope.h` as
`gfx-reset-scope.h`, and copy its `recovery-cycle.h`. The exact combined change
is also supplied as `retained-poweroff-owner.patch`; the command-only change is
`recovery-poweroff-command.patch`. Build with `GFX_RESET_SCOPE_TRIAL` and
`GFX_POWER_OFF_SCOPE_TRIAL`. Remove `GFX_RESET_NATIVE_SEQUENCE_TRIAL`; the new
header rejects that incompatible profile. Existing mandatory gate1/gate2
startup admission, no startup work/shutdown/warm/release flags, and the cold
owner's module/lifetime pin remain required. Root separately owns the new
receipt, runner/preparer and actual module build.

## Admission and sole PM transition

Typed commands are only `stop`, `sample`, `gfx-snapshot`, and `gfx-poweroff`.
The distinct preprocessor branch rejects every other command with `-EPERM`;
the old reset, recovery, control, trace-off and submission routes are absent
from the compiled profile.

`stop` seals packet publication and clears ASC START at most once, without
management packets or receive draining. It observes START clear and the matched
native idle predicate `(STATUS48 & 3) != 0`; these are admission observations,
not access-cessation proof. Before power-off, the owner must retain all174
pages, context, published mappings, consumer and MMIO mapping metadata, have no
work, empty36 work cursor words, inactive256 TA entries and equal consumed
control cursors32..128. It requires phase0 or2, a completed packet-free stop,
held PM ownership, runtime-PM enabled/active, exactly one usage reference and
no runtime error. The provider pre-snapshot must be valid, software domain ON,
ACTUAL/TARGET15 and RESET/DEV_DISABLE/PS_RESET/BUSY clear.

Every explicit `gfx-poweroff` consumes its gate, including precondition or
pre-snapshot refusal. It seals the receive worker under the shared mutex. On
eligible entry it records the PM attempt, clears local `held` ownership before
calling `pm_runtime_put_sync_suspend` exactly once, then retains all pages,
mappings, consumer and module on every result. RPM_GET_PUT consumes the usage
reference even when suspend reports an error. There is no compensating get,
second put, detach, disable, unmap, free, restart or work publication.

## OFF observations and diagnostics

The sole attempt records before/after usage count, runtime status/error and
enabled/active/suspended state. Post-call driver snapshots are bounded to101
samples, with at most100 `usleep_range(1000,1100)` delays. Logged
`poll_min_delay_us` is the requested minimum delay total, not an elapsed-time
guarantee or a bound on the synchronous suspend call. A read error stops that
poll. Every read preserves return/error/validity, software domain state and a
raw word only when valid.

`provider_off_observed` requires a valid error-free snapshot with domain_on0
and `(word & 0x90001cff) == 0`: ACTUAL0, TARGET0, AUTO28 clear, RESET31,
DEV_DISABLE10, PS_RESET12 and BUSY11 clear. Historical bits8/9 are excluded.
This differs from `accounting_ok`, which requires enabled runtime-PM, usage0,
suspended/inactive state, no runtime error and `held=false`. A negative PM-call
result remains the operation's result even if OFF is observed. Successful PM
return with still-ON or mismatching provider state times out; successful provider
OFF with inconsistent accounting returns `-EIO`. No return grants restart or
memory release.

After the consumed explicit gate, even when it refused before a PM call, every
diagnostic uses only safe provider snapshots, software accounting and retained
DRAM. It never reads ASC, SGX or mailbox registers. `sample` and `gfx-snapshot`
remain available; a subsequent `stop` performs no hardware write/read and is
idempotent only if packet-free stop had already completed. The receive worker
cannot drain or reschedule once sealed. Existing DRAM captures remain valid
without a live PM reference; root's separate wrapper must exclude any powered
GPU/ASC sampling helper from post-attempt capture.

OFF plus stable qualified DRAM can strengthen a scoped observation. It does not
establish outstanding transaction completion, private-cache writeback, UAT
drain, all GPU-engine cessation, fresh firmware DATA or repeatable restart. All
joined backing remains pinned. Read the frozen boundary evidence in
`docs/evidence/2026-10-09-gfx-native-poweroff-boundary.md` before a future trial.

## Actual-C RAM replay

`test-gfx-poweroff-owner.py` extracts the actual integrated idle predicate,
DRAM state logger, receive worker, full new header and typed command handler.
Its harness replaces PM, snapshot API, transport/MMIO and DRAM accesses with
recorders; it does not access hardware. Run it with `--output` for a bound report.
The ASan/UBSan replay verifies admission, one attempt, errors and post-attempt
MMIO exclusion, not kernel concurrency, genpd callback execution, hardware OFF,
coherence, isolation/drain or restart.
