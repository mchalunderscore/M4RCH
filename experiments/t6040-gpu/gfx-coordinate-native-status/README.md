# Native STATUS0 owner trial

This separate kit follows the selected Apple request-first STATUS0 branch while preserving the frozen execution bridge, draw, once-only intents and retained lifetime. STATUS0 skips ACK-wait; the diagnostic ACK preflight remains. It proves neither inactivity nor an acknowledgement.

Read `docs/evidence/2026-10-09-gfx-native-status-preparation.md` and the current `/boot/GPUC003/ASTRA-RESTART.md` first. The loaded owner on boot493814fd remains pinned before firmware START. No graph command, retry, PM change, cleanup or new load is admitted there. Root alone performs hardware operations; subagents stay offline.

Prepared candidate: `out/gfx-coordinate-native-status/candidate`. A normal fresh boot is required. The installed kernel and GRUB default5 are unchanged.

After the fresh boot, root performs the read-only preflight, saves its result once, then makes ONE cold attempt:

```sh
sudo -n python experiments/t6040-gpu/gfx-coordinate-native-status/preflight-fresh.py out/gfx-coordinate-native-status/candidate out/gfx-coordinate-native-status/fresh-preflight.json
sudo -n python experiments/t6040-gpu/gfx-coordinate-native-status/run-root-native-status.py out/gfx-coordinate-native-status/candidate --graph --run
```

A failed preflight does not admit the cold attempt. Inspect saved metadata before making a distinct correction. The cold runner independently checks native ADT, loaded owner identity and lifetime. Early/unknown startup admits no commands; it preserves the consumer, PM reference and acquired resources.

Only qualified healthy startup may use `run-native-status.py CANDIDATE COMMAND`. It preserves initial two idle recovery cycles; another successful `recover` yields the required four before `trace-off` and ONE `submit`. Successful cursors alone do not prove rendering. `analyze-checked-execution.py` binds the exact candidate, graph metadata, original TEXT and final captures before delegating to the frozen target/cursor analyzer. `analyze-completion-evidence.py` separately catalogs changed owned ring slots and numeric command associations; inspect receive/completion/stamp evidence independently.

Idle failures allow only the typed retained diagnostics and no-work packet-free STOP/OFF contingency admitted by the wrappers. A known returned STOP/EAGAIN can be reconciled by the exact module/receipt-bound `confirm-stop.py` using the next successful read-only snapshot. It writes only durable host metadata, never another STOP. Unknown/short/interrupted operations remain sealed. OFF requires complete ON coordination, STOP and native physical prerequisites before the sole PM put.

Every work intent closes further STOP/OFF/reset/restart/free/unload, even if publication later fails. The healthy RX worker is preserved; typed post-work diagnostics never drain the mailbox. No warm START/INIT retries or allocation retirement are admitted.

Offline qualification covers276 core and56 adapter actual-C cases under ASan/UBSan,593 Python cases including51 mocked cold flows, the unchanged178-case dispatcher, and the actual historical STOP pair plus17 negative variants. It establishes no live recovery, reset, teardown, DMA/UAT retirement, cache coherence or rendering.
