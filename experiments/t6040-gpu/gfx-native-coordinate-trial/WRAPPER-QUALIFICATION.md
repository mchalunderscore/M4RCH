# Offline wrapper qualification

Run without sudo:

```sh
python3 experiments/t6040-gpu/gfx-native-coordinate-trial/test-coordinate-runners.py
```

The suite loads the actual SHA-guarded thin transforms and executes their admission/intent logic with temporary files and simulated external operations. It reconstructs the pinned Linux OF fixture in temporary files. It performs no hardware, module, privileged or current-candidate action.

Final qualification: **353 cases passed**, including 114 inherited wrapper cases and 49 actual cold-main flows. The source-bound receipt and limits are in [the evidence note](../../../docs/evidence/2026-10-09-gfx-coordinate-wrapper-qualification.md) and its JSON pair. The full normalized traces are saved to ignored `out/gfx-native-coordinate/wrapper-qualification.json`.

The tests qualify wrapper refusal/control flow, not MMIO effect, native policy equivalence, successful OFF, DMA retirement or restart. They also record that canonical new receipts are rejected by historical runners, but a manually mixed receipt can be accepted by the frozen historical validator. Paired runners reject mixed receipts.
