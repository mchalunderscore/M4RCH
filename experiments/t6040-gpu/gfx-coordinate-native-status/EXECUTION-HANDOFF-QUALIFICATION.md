# Checked saved execution analysis

Use the separate `analyze-checked-execution.py` for the exact prepared native-status candidate. It binds the saved receipt/preparation, artifacts, sources, draw backing, graph fixture/metadata and downstream tools before invoking the unchanged pinned `analyze-execution.py`. It requires final objects/owned capture sizes and digests, the dmesg digest, and copied TEXT matching the original cold-session boot/receipt/raw TEXT identity. It refuses unbound firmware DATA files and writes outside the frozen candidate. The bound files are rechecked after delegation; these checks do not form an atomic filesystem snapshot.

The frozen analyzer omits a graph metadata hash comparison. The direct RAM replay demonstrates the consequence: changing an in-bounds cursor address changes its reported root cursors from `[1,2,3]` to `[2,2,3]` while returning success. The checked launcher refuses that same mutation before downstream analysis. All frozen sources and candidate bytes remain unchanged.

The 21 direct and 36 checked cases use immutable candidate bytes and CPU-authored synthetic capture data produced through the actual resident capture function with native reads/dmesg intercepted. Positive runs execute the actual owned-work analyzer and target sample checker, proving `work/target-after.bin` and `work/result.json` handoffs into `target-samples.json` and `summary.json`. Eight fabricated passing pixels still leave GPU execution and retirement false.

Pass the resident operation directory containing `attempt.json` and `final_capture`. Timed `sample-01s`/`05s`/`15s`/`30s` directories have no independent attempt report and are not directly admitted by these launchers. Receive/completion evidence needs the separate supplemental tool. `live_*` arrays are boot log history, not newly qualified hardware observations after submit. Firmware DATA is absent from the resident capture protocol.

[Bound evidence](../../../docs/evidence/2026-10-09-gfx-native-status-execution-handoff.md) records source, fixture and ignored receipt hashes. No new native execution, rendering, synchronization, cessation, retirement or restart is established.
