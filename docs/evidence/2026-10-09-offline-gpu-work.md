# GPU work completed without rebooting

This checkpoint adds offline tools and contracts against source baseline
`d98fee4`, matched AGX353.14 and saved boot1730 captures. No GPU command,
module load/unload, live sysfs access or hardware trial was performed. The
sealed session retains its backing. The prepared dispatch candidate's module,
graph and build receipt are unchanged.

| Work | Result | Validation |
| --- | --- | --- |
| Native scheduler-state construction | The seed matches the native prefix when the supplied owner byte is2. Config5a is PID,5e subpriority,56 a QoS hardware-buffer ID. Current config0/0 conflicts with staged PID1/2 and subpriority1. Task/VM and QoS ownership remain unresolved. | 265 successful allocations,34 failures,3 actual bounds traps,256 joined configuration chains; full-byte comparisons and receipt-corruption rejection. Root reproduced the final proof byte-identically; independent review passed. |
| Recovery after submitted work | Bounded128x16 submitted-timestamp table,256x8 TA recovery records, stamp-index/operand extraction and pre/post-resume host obligations. Both saved tables are zero; the active path is unexercised. | 47 checks including actual native/FW instruction fragments and malformed/boundary inputs. Capture receipt and snapshot identities are bound. Root rerun passed. |
| Completion identity and stamp arithmetic | Separate command-class reads, KSM timelines, notification bits, stamp generations, host fences and resource lifetimes. Native forced completion is bookkeeping, not hardware execution. External event services remain a boundary. | 3,072 bounded actual-instruction RAM cases plus15 decoder boundaries. Root reproduced the final proof byte-identically. |
| Recovery dispatch ledger | Pinned capture/proofs, token/phase/prefix chronology, native pending-mask invariants and conservative entry/exit pairing. Old capture still has marker7794 and no bit25 records; bit1 was not requested there. | 17 adversarial groups, including stale requests, repeated cycle IDs, duplicate/malformed entries, bad timestamps and journal failures. Independent review found and verified fixes for three pairing/request edges. |
| Standalone ABI terminology | Channel word48 is named PID; word40 is identified as subpriority. Serialized values and prepared artifacts are unchanged. | All10 existing Rust codec tests pass. |

Exact numeric identities and final source/output hashes are in the adjacent
`2026-10-09-offline-gpu-work.json`. Private binaries, full disassembly and raw
captures remain outside tracked files.

The new source tools are:

- `experiments/t6040-gpu/audit-native-scheduler-state.py`
- `experiments/t6040-gpu/analyze-recovery-bookkeeping.py`
- `experiments/t6040-gpu/analyze-completion-identities.py`
- `experiments/t6040-gpu/analyze-recovery-dispatch.py`

Read the neighboring native-scheduler-state, recovery-bookkeeping-contract
and completion-identity-contract reports for runnable offline commands,
service boundaries and exact byte/range qualifications. The dispatch analyzer
accepts an initial capture and a new output path:

```sh
python experiments/t6040-gpu/analyze-recovery-dispatch.py CAPTURE OUTPUT
python experiments/t6040-gpu/test_recovery_dispatch.py
```

It defaults to `CAPTURE/../graph-receipt.json`; `--layout` supplies that exact
receipt explicitly. It preserves all raw-observation limitations and always
requires manual source attribution. No analyzer output grants publication,
recovery, retirement or release permission.

Useful further offline work is to join the actual scheduler-owning task and
its mappings to UAT, qualify QoS ID registration and intended PID/subpriority
policy, and implement a retained host registry connecting commands to stamps,
fences and recovery records. A consistent config can then be prepared against
that registry without inventing identities. Current candidate values were
preserved rather than applying partial policy changes.

The exact cause of the idle phase2 stall still needs live ACK observations.
Runtime scheduling, GPU cache/DMA behavior, execution, pixels and safe memory
retirement remain unverified. No failed warm-wake sequence was repeated.
