# Native command probe: version 2 outcome decision

Offline decision aid for a future retained-owner trial of `apple_pmgr_t6040_gfx_native_probe()` on `7.1.13-m4rch-gpu-native-reset`. The native trial has not run. No hardware or source changes were made for this note. It uses the frozen API proposal receipt SHA256 `35524874fce0ae31c8d6376d9a4b7880d367a3024cdbc189b77b6025a1f942ad`, PMGR C `04910407755d029a2acd131f873359bd14983ace946a469725612883835abb61`, header `4fbdca1e18ed9c3ee030bad9a94f35c2f70b213d038dfb0555350f35809df9a0`, and additive patch `5df46ea05dbf84d0245a6a74b97f309ca07c1b1d54d3848497ee7cf430bd5264`. The companion JSON pins the evidence and current owner interpretation.

## Classify delivery before considering reset scope

| Saved outcome | Established fact | Interpretation/action |
|---|---|---|
| Owner refusal, `attempted=0`, sealed | The owner did not enter the API; its explicit command consumed the gate. | Preserve the refused precondition. Retain backing; no retry. |
| Complete API receipt has `command_attempts=0` and an error | No native `regmap_write` call was reached. Provider/reference refusal, failed BEFORE read, or inactive/forbidden BEFORE state can cause this. | Record the specific provider/read/reference or power condition. Missing BEFORE alone is less decisive than a complete zero-attempt receipt. |
| Any command attempt plus nonzero primary or cleanup error | A write may have committed even if it returned an error. Later valid reads do not erase that uncertainty. | Use every command's attempted bit, desired full word, and write error; keep the owner sealed and backing retained. |
| Errored cleanup release, failed/timeout cleanup release check, or `release_command_verified=0` | The final forced-release command/check is unverified. The implementation does not attempt cleanup AUTO restoration after an uncertain release. | Preserve attempted inhibition/release and raw observations. The actual inhibited state can itself be uncertain if bus writes failed. |
| Primary error, but cleanup release command/check succeeds and policy is observed restored | Cleanup recovered the software command/policy checks; the failed primary operation remains failed. | `cleanup_error=0` or restored policy cannot convert that operation into a reset-scope success. |
| Return and both common errors zero, `sequence_completed=1`, `release_command_verified=1`, restored policy, complete consistent primary receipt | The defined command sequence and release/policy checks completed. | Compare the saved ASC and firmware-owned shared observations. No physical reset acknowledgement, access cessation, backing release or restart follows from return0. |
| Interrupted/lost/inconsistent result | The extent of command delivery is unknown. | Treat as an uncertain consumed attempt. Preserve the receipt gap and perform no new pulse. |

Prewrite power refusal requires domain ON and ACTUAL/TARGET15, with RESET31, DEV_DISABLE10, PS_RESET12 and BUSY11 clear. Existing reset references are refused before a register read. Command attempt bits are set **before** each bus call; an unset bit in a complete receipt proves that call was not reached. An invalid later read field never proves an attempted write was absent.

## Read and command provenance

The eight command slots are INHIBIT, DISABLE, ASSERT, RELEASE, RESTORE, CLEANUP_INHIBIT, CLEANUP_RELEASE, CLEANUP_RESTORE. Every desired value is a complete forced 32-bit write. Normal primary attempts are `0x1f`: inhibited BEFORE image, `B|0x400`, `B|0x80000400`, `B`, and `B|original_auto`. `B` comes from the fresh qualified AUTO-held read with historical bits8/9 cleared; cleanup has the reviewed BEFORE fallback if that read failed.

The eight read slots are BEFORE, AUTO_HELD, DISABLED, ASSERTED, RELEASED, FINAL, CLEANUP_RELEASE, CLEANUP_FINAL. Normal primary read attempts are `0x3f`, and `common.valid=0x6f`: there is no separate DEASSERTED stage. Primary write errors are all zero; `base_from_auto_held=1`; disable and pulse delays are each1us. Poll stages may take multiple reads, with at most101 reads/100us deliberate delay each.

ASSERTED is a diagnostic raw read. Neither DEV_DISABLE10 nor RESET31 must read set. DISABLED checks active/inhibited power, PS_RESET/BUSY clear and RESET clear while allowing either bit10 value. Successful explicit release plus active/inhibited power and RESET/DEV_DISABLE/PS_RESET/BUSY-clear reads qualifies `release_command_verified`. Final policy restores original AUTO; ACTUAL may then gate when original AUTO was set. Historical flags, valid fields and command bits are not physical coverage predicates.

`common.valid` retains successful samples, including a timed-out poll's last sample. Per-stage read attempts/counts and last bus `read_error` show provenance. A timeout can have `read_error=0` and valid data; the overall operation/cleanup error and raw predicate still matter. CLEANUP_RELEASE and CLEANUP_FINAL share `common.cleanup_final`/valid`0x80`. A later final read failure leaves the earlier successful release value intact; a later successful final read replaces it. Never interpret common valid`0x80` alone as the latest stage succeeding. `release_command_verified` reports a successful forced command and checked raw conditions at its boundary, never proof of a physical line or every GPU bus master releasing.

Every branch permanently seals the owner/wrapper's one-attempt gate. The remaining admitted actions are bounded sampling, read-only `gfx-snapshot`, and packet-free stop through the retained owner. No branch permits a second pulse, warm START/INIT, a new graph, unload, PM-reference release, unmap or backing free.

## Compare activity without inventing a retirement boundary

Preserve the complete command/read receipt, before/after ASC CONTROL40/CONTROL44/STATUS48, recovery phase/control cursors, timestamped logs and owned-object captures. The existing immediate and bounded later samples can detect changes in already qualified firmware-owned shared fields. Continued firmware-owned writes are positive evidence of continued access. Stable fields show only no observed progress during that interval; cache-aware host copies cannot exclude private dirty cache lines, unsampled engines or future writes.

The receive journal is a **host** capture. Sealing cancels its worker and stops host publication/draining, so unchanged journal count/status/doorbells is expected even if firmware still produces messages. Compare firmware-owned fields whose layout and ownership are already qualified, rather than treating the frozen host journal as firmware cessation.

Matched AppleASCWrapV6 idle is `(STATUS48 & 3) != 0`, accepting either low bit. Passing that predicate plus CONTROL44 START bit4 clear supports only the sampled ASC stopped/idle observation. It does not cover all GPU engines, UAT/DART translations, caches or outstanding DMA. Packet-free stop clears START once and retains all174 pages; it adds no DMA retirement proof.

A changed ASC/shared observation is a useful scope lead. Whole-GPU cessation still requires a qualified completion/isolation-and-drain boundary for every relevant bus master. A fresh execution also needs a coherent firmware DATA/entry/mapping/mailbox lifecycle; command delivery and bounded memory stability do not reconstruct it. These gaps cannot be resolved by repeating failed warm wake trials. This guide records no native hardware result and authorizes no backing reuse or release.
