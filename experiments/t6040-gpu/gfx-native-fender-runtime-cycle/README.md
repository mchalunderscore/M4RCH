# Native Fender runtime cycle, v19

The frozen v18 trial on boot `2529a76a-a0ac-4de7-95f8-71b42181042b` accepted control33 and verified the native Fender enable RMW at SGX+d06030 (6→0). Its next physical snapshot was `0x1400034f`: TARGET15, ACTUAL4 and AUTO enabled. The inherited strict ACTUAL15 guard refused before publishing a draw, so the capture did not admit a postdraw cycle.

V19 preserves the native Fender operation and corrects the read-only runtime admission after its successful completion. It requires TARGET15, no RESET/DEV_DISABLE/BUSY/PS_RESET, and the known ACTUAL states 0, 4 or 15; gated states 0/4 also require AUTO. Before Fender completion, the original strict active predicate applies. The selected retained-epoch cycle uses the same runtime predicate only at `admission-before` and `before-off`. Physical OFF, PM accounting, and fresh ON after a cycle keep their original strict checks. No new MMIO or PM writes are introduced by this correction.

Application/control/trace/idle/identity checks retain their existing predicates and now log the precise refused operands. One draw, the 15-second observation window, immutable full capture before one native202/NMI timeout fallback, and management-only rejoin remain the v18 path. All 174 pages stay retained. Management rejoin does not prove reusable application queues, DMA retirement, or a rendered triangle.

The parser binds runtime rows to fresh caller snapshot operands and the selected order: four strict cold guards followed by two dynamic guards around draw-intent; cycle admission has only the two selected dynamic phases. Runtime C qualification runs the actual immutable helper under sanitizers. Changed host tests cover the new policy and order, strict OFF/fresh ON negatives, consumed-boot refusal before candidate/live reads, and one intercepted capture-before-cycle main flow. Frozen v18 Fender45/host21/1 and v17 C64/preASC39/host41/10 receipts are composed without rerunning them. Fixture composition and actual production source projection are recorded separately.

The root hardware owner prepares/builds/finalizes the distinct candidate. After qualification, a fresh boot admits one trial:

```sh
sudo -n python3 /home/alice/Desktop/m4rch/experiments/t6040-gpu/gfx-native-fender-runtime-cycle/preflight-fresh.py /home/alice/Desktop/m4rch/out/gfx-native-fender-runtime-cycle/candidate /home/alice/Desktop/m4rch/out/gfx-native-fender-runtime-cycle/fresh-preflight.json
sudo -n python3 /home/alice/Desktop/m4rch/experiments/t6040-gpu/gfx-native-fender-runtime-cycle/run-cold-render.py /home/alice/Desktop/m4rch/out/gfx-native-fender-runtime-cycle/candidate --graph --run
```

The host saves the draw and cycle evidence under `candidate/asc-graph-init/boot-<UUID>/`. The complete target output is `target-after.bin`, with `target-after.png` as its provisional-layout preview. The once-only cycle follows a durably sealed capture; its uncertain outcome is never replayed. Frozen v18 and earlier consumed boots are rejected before candidate or live reads.
