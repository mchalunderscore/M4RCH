# Native Fender disable before OFF, v20

The frozen v19 trial on boot `f4a7b737-ed3d-4851-8fcd-cac56eb233d7` reached one draw after the corrected dynamic runtime guard and native Fender enable. Firmware consumed the draw roots, but the target/completion/queue captures and terminal pending-bit28 trace signature matched v17/e728. Native202 timed out; NMI reached idle, then CPU stop, coordinate OFF and PMput succeeded. All101 strict physical OFF samples retained BUSY0x800 (`0x0f000b00`), preventing ON/restart.

V20 tests one distinct teardown hypothesis: transfer Apple's native Fender disable operation, a fresh SGX+d06030 RMW `old|4`, immediately before OFF sealing. The sole new caller follows successful CPU stop, fresh runtime ON, coordinate ownership and the exact alias check. It precedes off-intent, coordinate OFF and PMput. The helper checks retained174-page/PM/mapping identity, takes another fresh physical snapshot at `fender-off-before`, applies the existing runtime predicate, verifies GPU identity, preserves other register bits, reads back the single write, and executes the barrier. It runs once; a refused or uncertain operation cannot be retried.

The primitive is source-backed; its placement is an experimental transfer into the existing retained lifecycle. This does not reproduce Apple's complete native poweroff implementation. Strict physical OFF, PM accounting, and fresh ON/rejoin checks retain their v19 predicates. Draw/start/application/runtime/NMI logic is inherited without behavioral changes. ACK cleanup, forced PMGR writes, direct kicks, application replay and backing release are outside this trial.

The changed host parser requires the disable proof after stoppedCPU/before-off and before off-intent. Actual helper C65 and changed host cases/one intercepted capture-before-cycle flow are qualified. Frozen runtime829/host36/1, Fender45/host21/1 and C64/preASC39/host41/10 receipts compose without rerunning them. The new actual-C helper fixture emits intent/runtime/op/complete; its shim counts the fresh snapshot. The independent combined fixture projects the unchanged v19 C snapshot logger shape to the new phase and exact runtime operands. Actual production source projection binds the real snapshot call and logger separately.

Root builds and finalizes the distinct candidate. After qualification and a fresh boot, the root hardware owner admits one trial:

```sh
sudo -n python3 /home/alice/Desktop/m4rch/experiments/t6040-gpu/gfx-native-fender-off-cycle/preflight-fresh.py /home/alice/Desktop/m4rch/out/gfx-native-fender-off-cycle/candidate /home/alice/Desktop/m4rch/out/gfx-native-fender-off-cycle/fresh-preflight.json
sudo -n python3 /home/alice/Desktop/m4rch/experiments/t6040-gpu/gfx-native-fender-off-cycle/run-cold-render.py /home/alice/Desktop/m4rch/out/gfx-native-fender-off-cycle/candidate --graph --run
```

Evidence is saved under `candidate/asc-graph-init/boot-<UUID>/`. The full target is `target-after.bin`, with `target-after.png` as the provisional-layout preview. The host seals the complete capture before its one cycle command. Current f4 and earlier consumed boots are refused before candidate/live reads. A management-only rejoin would still leave rendering, DMA retirement and reusable application queues unproved.
