# Cold render candidate

This version13 profile starts a fresh owner, completes its own cold AP20 exchange and application endpoint starts, publishes the original root, consumes one new opcode22 control record (cursors32→33), and publishes the preserved two-record TA/3D draw once. It omits class86 recovery and any recovery-count prerequisite. The loader automatically captures the retained result; no resident draw command is needed.

The source observes the draw immediately and at scheduled offsets100ms,1s,5s and15s. These are actual timed samples with a finite poll bound. Each phase saves raw register rows, output/ring change counts and receive-journal observations. The host saves final full graph, all174 owned pages, the full64×64 RGBA8 target, software completion page, four queue pages and four hardware completion pages. It does not save full-page snapshots at each sample.

The analyzer binds the new operation delta, candidate receipts, loaded owner note, firmware TEXT and exact dump extents. Failed and incomplete source sample boundaries retain their raw diagnostics separately from successful pipeline qualification. Firmware cursor movement, raw hardware state, decoded completion and pixel content are distinct evidence levels. Full-buffer triangle comparison derives from the pinned vertex/shader recipe under a provisional linear layout; edge exactness is excluded and a synthetic matching image proves no hardware rendering.

The owner, PM reference and backing remain retained after success, failure or partial publication. No submitted-work OFF, PMput, unload, free, retry, warm restart or recovery-phase write is admitted. A previously consumed boot is refused before candidate or live-content reads. Replacing the currently loaded owner requires a fresh boot; this profile does not attempt to clear its failed state.

The selected candidate is `out/gfx-cold-render/candidate-v2`, finalized on C qualification v8 and host qualification v4. The unchanged compiled module was copied from the preserved prior candidate with explicit custody pins; it was not rebuilt for the host diagnostic correction. The prior Qv3 finalization remains historical. Do not re-finalize either existing output.

On an authorized fresh boot, root runs:

```sh
sudo -n python3 experiments/t6040-gpu/gfx-cold-render/preflight-fresh.py \
  out/gfx-cold-render/candidate-v2 out/gfx-cold-render/fresh-preflight.json
sudo -n python3 experiments/t6040-gpu/gfx-cold-render/run-cold-render.py \
  out/gfx-cold-render/candidate-v2 --graph --run
```

Run the loader only after preflight succeeds, once on a fresh boot. Offline qualifications use actual C-emitted logs and intercepted launcher entry points; they perform no module build, load or GPU access. See `docs/evidence/2026-10-10-gfx-cold-render-prepared.md` for the selected build, source and review identities.
