# Native powergate Python qualification

This separate family admits only `sample`, `gfx-snapshot`, and one `gfx-powergate`. The command combines the owner's sole management202 request/ACK, checked CPU stop, paired PMP/PMC OFF, and sole PM put. No automatic powergate, old STOP/OFF, control, recovery, trace-disable, submit, reset, warm start, release, or unload operation is exposed.

`test-powergate-runners.py` exercises actual generated startup and resident paths with all native access intercepted. The frozen native STATUS startup/parser/flash helper is a SHA-bound input through a local receipt view; old candidates remain untouched. Final qualification passed 196 cases and 45 cold-main flows. Actual resident main, loaded GNU-note validation, fsynced command intent, repeated/interrupted writes, lost-state history, and capture/journal failures are covered. These are RAM results, never a GPU success claim.

Run qualification to a new output path:

```sh
python3 experiments/t6040-gpu/gfx-native-powergate/test-powergate-runners.py NEW_OUTPUT_JSON
```

The frozen final receipt is `out/gfx-native-powergate/wrapper-qualification.json`. `finalize-powergate.py CANDIDATE OWNER_QUALIFICATION` binds the separately built source and C qualification and creates `asc-root-envelope/build-receipt.json` plus `powergate-preparation.json`; those outputs must not already exist. `preflight-fresh.py CANDIDATE NEW_OUTPUT_JSON` is read-only and refuses boot 94cb and conflicting owners. Root performs finalization and any later hardware operation.

See [portable evidence](../../../docs/evidence/2026-10-09-gfx-native-powergate-wrapper-qualification.md) for exact pins and limits. Frozen helper files are not to be edited during a pending trial.
