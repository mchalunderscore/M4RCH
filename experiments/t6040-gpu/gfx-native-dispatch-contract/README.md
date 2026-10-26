This is the distinct v15 cold draw experiment, `gfx_native_dispatch_contract_scope`. It copies the saved draw with four native configuration getter bytes corrected: queue 0 PID/subpriority 1/1 and queue 1 PID/subpriority 2/1. Those values are supplied process/policy operands; they do not establish a native identity allocation or a diagnosed rendering blocker.

The owner proves fresh control cursors 33/33/33, restores the shared trace mask from 0 to 3 once, then publishes one draw and records the existing 15 second observation window. It performs no scheduler request or ACK intervention. The host joins the actual C fixture and requires the restore between ready33 and its own sample0. PM, owner and all backing remain retained after the attempt.

The launcher saves full objects, owned pages, receive journal, RGBA target and PNG before it interprets logs. Exact prefix or unique exact suffix overlap binds the operation delta; ambiguous logs still retain the raw diagnostics. It then reads fixed reserved DATA at PA `0x10001d44000` for `0x138000` bytes and page tables at PA `0x105fff78000` for `0x40000` bytes. Each read loads and unloads only the pinned `gpu_data_sample` module. The loaded sampler must have the selected GNU note and refcount 0 before reading or unloading; the owner GNU note, refcount 1, boot and kernel are checked before capture, immediately before sampler unload and afterward. Failed reads are recorded without retry. A sampler custody mismatch or owner change leaves the sampler resident and stops the batch; incomplete unload also stops it. These RAM samples are non-atomic and do not prove IOP cache writeback or current PC.

The current eff8 boot is refused before candidate/live reads. After a fresh boot, use the selected candidate and host files pinned by `cold-render-preparation.json`:

```sh
python3 experiments/t6040-gpu/gfx-native-dispatch-contract/preflight-fresh.py out/gfx-native-dispatch-contract/candidate out/gfx-native-dispatch-contract/fresh-preflight.json
sudo python3 experiments/t6040-gpu/gfx-native-dispatch-contract/run-cold-render.py out/gfx-native-dispatch-contract/candidate --graph --run
```

Output is under `candidate/asc-graph-init/boot-<boot-id>/`. `target-after.png` preserves the full target, and `attempt.json` records qualified and uncertain outcomes. `analysis/result.json` keeps pipeline, trace, raw observations and retained RAM provenance separate from GPU execution and rendering, which remain unverified. Never reload this owner or repeat a consumed boot.

Offline qualification uses `test-host.py --source <prepared-owner> --owner-qualification <actual-C-report> --output <new-report>`. It runs the new trace/source and retained RAM paths only, composing the frozen v14 51 host cases and prior v13 qualifications. The finalizer binds that report, the selected C report, the exact four-byte recipe, the owner build and the cache-invalidating PT sampler source/build custody.
