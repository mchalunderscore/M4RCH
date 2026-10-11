# Native render publication integration checkpoint

The current boot remains 14343c22-f598-4eae-974a-b0edf7009530, consumed by v23.
No GPU hardware actions occurred during this integration work. Frozen v24
remains the prepared fresh-boot full-power triangle trial; these normal Gravity
changes do not replace or modify that candidate.

Two source-resolved corrections are now implemented:

* The connected command/SKU/KSM builder retains the original submitted
  scheduler timestamp and encoded queue ID. Its `write_transport` constructs
  opcode14 from those identities. The next scheduler counter is returned
  separately and must never substitute for the submitted timestamp.
* A new Gravity stage allocates separate hardware scheduler entry backing,
  maps every page, and places those device/firmware views in opcode15. The
  existing eight-byte firmware pointer ring remains separate. Native KSM
  records staged in Work must be copied into the actual hardware entry slot;
  firmware publication uses the opcode14 transport record address.

The native typed opcode14 producer matches both actual TA and fragment store
slices in 256 cases with 256 short-buffer refusals. The composed builder passes
80 jobs, 80 transport checks and 80 submitted-timestamp checks, alongside 240
job failure cases and 2400 named register checks. The retained Work layout
reserves separate transport storage and verifies 3840 nonoverlapping extents.

The new stage is `out/gpu-gravity-normal-render-transport-v9`, based on the
native PM owned allocator stage. Its actual kernel module builds successfully
with 42 existing warnings and zero errors. All 78 source files agree with the
build-owner copy. It is uninstalled, unloaded and gated; no complete native
render caller or hardware acceptance is claimed.

Next integration work is the actual hardware entry enqueue, padding/pending
and completed accounting, and the native PM/command/transport caller branch.
Use the saved scheduler wrapper/sequence evidence and queue-role handoff.
Queue capacity256 is an explicit Linux experiment, not inferred platform
configuration. Scene geometry and scheduler mode remain real owner inputs.
Do not resurrect the former contract that published Work's KSM pointer through
the firmware pointer ring. Retain allocations, mappings, identities and scene
leases on ambiguous publication or retirement.

Evidence: native-render-job-v9.json, native-postkick-v9.json,
native-work-layout-v9.json, native-queue-role-integration-v9.json and
native-render-transport-build-v9.json in this directory.
