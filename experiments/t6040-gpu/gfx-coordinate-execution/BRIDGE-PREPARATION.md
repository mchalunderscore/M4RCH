# Deferred execution source bridge

This kit extends the frozen paired coordinator in a separate source directory. It does not alter or replace the next no-work trial. Source preparation is offline and performs no build, load, submission or hardware operation:

```sh
python3 experiments/t6040-gpu/gfx-coordinate-execution/prepare-execution-owner.py \
  --source out/gfx-native-coordinate/candidate/asc-graph-init \
  --destination out/gfx-coordinate-execution/prepared-owner
```

The destination must be new. Exact hashes bind the frozen dispatcher, owner, core, adapter, scope helper, recovery contract, graph, graph receipt and authored draw inputs. Every copied input/output hash is recorded in `execution-owner-source-receipt.json`. Only `Makefile` and `recovery-cycle.h` change; the new flag is `GFX_COORDINATED_EXECUTION_TRIAL`.

The draw already exists. The latest actual work trial was `out/owned-hw-completions/live-candidate`, boot `520da35a-487e-4575-97b3-af12afa2936c`: four hardware completion descriptors were installed, but no completion-ring or target bytes changed. The current coordinator retains that `backing.bin`, `job-data.h`, and `render-data.h`, plus all 174 owned pages. Its idle graph has zero work cursors/rings; `recovery-contract.h` retains the two deferred 24-byte TA/3D work records.

The separate profile restores the existing `control`, `recover`, `trace-off` and one `submit` dispatcher. Startup still publishes no work. Submission requires at least four completed idle recovery cycles, confirmed native trace-off, idle request/phase fields and a consumed current control record. The existing ring0/ring1 copy, cache-maintenance, producer publication and EP33 class83 notification sequence is preserved.

Every recognized submit consumes a permanent intent before any hardware-facing read, even if a later prerequisite refuses it. Any subsequent submit, control, recovery, trace-off, STOP, OFF or reset command refuses before MMIO. Only typed sample/snapshot diagnostics remain. Those commands use the existing no-work diagnostic helpers and do not drain the mailbox; the existing healthy asynchronous receive service remains active so the batch can complete. Before any work intent, the original packet-free STOP and sole paired OFF contingency remain available. Work intent authorizes no DMA retirement, PM release, restart, unload or reuse.

The actual-C dispatcher qualification and final build/receipt belong to separate steps. Source preparation alone is not a runnable or ready execution candidate. The frozen no-work coordinated candidate remains the next hardware trial.
