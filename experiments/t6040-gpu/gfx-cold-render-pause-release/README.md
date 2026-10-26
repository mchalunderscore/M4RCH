# One scheduler request-bit intervention

This separate version14 candidate tests whether request bit0 is blocking the already accepted cold TA/3D work. It preserves the cold AP/root, fresh control32→33, original draw and fifteen-second observation path. After the unique100ms sample, eligibility requires request3, ACK2, enables3/0, the four expected completion configurations, no fault, and no target or completion progress. It then writes request3→2 once, preserving bit1, and records readback plus later firmware rewrites.

ACKbit0 is already zero before this intervention. A completed request write does not prove GPU resume, native reason/mutex ownership, job completion or rendered pixels. The candidate writes no ACK, sends no extra work notification and performs no retry, restart, submitted-work OFF, PMput, unload or backing release. The owner and all174 pages remain retained after every outcome.

Root finalizes the built candidate using the selected actual C and host qualifications:

```sh
python3 experiments/t6040-gpu/gfx-cold-render-pause-release/finalize-cold-render.py \
  out/gfx-cold-render-pause-release/candidate \
  out/gfx-cold-render-pause-release/owner-qualification-v3.json \
  --host-qualification out/gfx-cold-render-pause-release/wrapper-qualification-v2.json
```

On the authorized fresh boot, run preflight, then the automatic single trial:

```sh
sudo python3 experiments/t6040-gpu/gfx-cold-render-pause-release/preflight-fresh.py \
  out/gfx-cold-render-pause-release/candidate \
  out/gfx-cold-render-pause-release/fresh-preflight.json
sudo python3 experiments/t6040-gpu/gfx-cold-render-pause-release/run-cold-render.py \
  out/gfx-cold-render-pause-release/candidate --graph --run
```

Boot1241 and all prior consumed boots are refused before candidate or live-content reads. An existing session also prevents another load. Results are saved under the candidate's `asc-graph-init/boot-<boot_id>/` directory.

The host checks the loaded owner identity, then saves the final full graph,174 owned pages, journal,64×64 RGBA8 target, completion page and four queue/hardware-completion pages before attempting log association. A strict prefix or unique exact saved-log suffix overlap can qualify the new source rows. Ambiguous or absent overlap leaves the full raw capture intact and marks association uncertain. Per-phase evidence consists of register rows and buffer-change counts; full-page dumps are final only.

The actual C fixture joins both the cold pipeline and typed intervention parsers. Host Qv2 passed51 new cases and11 intercepted main flows; frozen v13 qualifications compose without broad reruns. Those offline results establish no hardware rendering. Image comparison remains conditional on the source-derived provisional layout, and completion/retirement require separate evidence. All v13 sources, candidates and captures are preserved.
