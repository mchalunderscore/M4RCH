# Final native PWRGATE admission-drain checkpoint

The distinct candidate at `out/gfx-native-powergate-drain/candidate` is built,
finalized, reviewed and never loaded. Read the [final prepared evidence](../../../docs/evidence/2026-10-09-gfx-native-powergate-drain-prepared.md)
and `/boot/GPUC003/ASTRA-RESTART.md` for the current owner and exact commands.

Owner SHA256: `de75ef4b8c772a56de3026ceb622b940206ed7d0a1ac660a25cae323216681f3`.
Receipt SHA256: `393049662c9966922fda7f66cbfa1c762efc2f0840492042b581e96271a7b6a5`.
Preparation SHA256: `f0fbf1090d73aad478f5b06a76a2f3900d672834c83a4201e0d01103e03fd923`.

The W=1 build has no warnings or errors. Actual C ASan/UBSan checks pass85 cases;
targeted Python checks pass94 cases, including9 actual mocked cold-main flows.
Independent source/C replay and final receipt checks passed.

Current bootd841 has a consumed pre-request PWRGATE intent and retained174 pages;
its owner and sole PM reference remain held. Both currentd841 and old94cb boots
are refused. A normal fresh boot is required for one new trial. GRUB default5
and the installed native-reset kernel remain correct.

The only typed commands are `sample`, `gfx-snapshot` and one `gfx-powergate`.
The new probe records exact admission operands and services only bounded,
qualified EP32 notifications before requiring fresh RX-empty/TX-available
admission. Stale EP0, invalid/unknown/crash frames, bounds and changed operands
seal without another request. The nominal11ms jiffy deadline is not a guaranteed
wall-time bound. No work, restart, unload or backing release is admitted.
