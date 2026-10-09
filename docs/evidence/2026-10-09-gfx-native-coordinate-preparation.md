# Prepared paired PMP/PMC GFX power trial

The new candidate is built and qualified for a fresh normal boot. It has
not been loaded. Boot339b9e8e still has the attempted power-off owner and
all174 owned pages and published mappings/context/consumer retained, with its sole
PM reference already consumed. Its failed BUSY-clear and continued shared
producer result is unchanged. Do not load another owner on that boot.

The distinct candidate is `out/gfx-native-coordinate/candidate`; owner SHA
`a7b3f21acfa50fcc35dba6d46f86d575e166d562c4dd0c575e5d58fd7d26b7f0` and
receipt SHA `0afe3eed85958b124be56e7ed4c0f76595bf8271c016c44d47c4903ebe5a669c`.
It uses the installed7.1.13-m4rch-gpu-native-reset kernel. No kernel install,
GRUB change, hardware operation or reboot was performed for preparation.
The other seven helpers, prepared graph/backing and kernel bindings match
their prior hashes. All10 artifacts and17 owner sources were verified.

The experiment supplies the notifications missing from Linux's physical
PMGR transition. ON: physical ACTIVE, PMP request bit13/valid matching ACK,
PMC voter bit2 on three rails, then firmware START. OFF: packet-free STOP,
PMP request clear/valid matching ACK, PMC voter clears, then the one normal
PM put and strict OFF observation. These are selected native operations;
their causal effect on BUSY/firmware cessation remains an experiment. The
native dynamic-vote state, boot overrides and hardware policy equivalent
are unobserved. ACK is not a DMA retirement fence.

Actual-core182 cases, adapter/lifetime40 cases and wrapper353 cases pass;
the wrapper suite includes49 actual transformed cold-main flows. The full
W=1 module build passes. The native evidence pins50 bounded ranges and13
vtable bindings; root checked them and all11 input bindings. Linux
integration pins17 files.

The fresh cold runner uses12 native ADT pins plus a312-node Linux resource
layout guard with malformed-tuple checks and device type. Metadata mismatch
refuses before samplers/load; authoritative C aliases/reservations are
checked before coordinator mappings. Whole-word updates preserve the read
snapshot; external-writer atomicity is not claimed.

All ON refusals keep the module/consumer/PM and acquired resources pinned.
Known failed startup is recorded before graph access. Unknown, contradictory
or missing evidence, failed load, absent module, incorrect loaded GNU note
or zero lifetime reference cannot authorize graph reads, powered sampling,
cleanup or retry. A successful startup requires exact ON/owner/graph and
resident markers. Failed OFF coordination keeps held=true; successful
coordination alone does not grant restart or release. Existing post-OFF
PMGR/DRAM-only diagnostics and strict word mask remain unchanged.

Use only `gfx-native-coordinate-trial/run-root-coordinate.py --graph --run`
for the new cold owner and `run-coordinate.py` for typed operations.
If STOP returns the known EAGAIN, preserve it and obtain only the next
read-only snapshot. The separately guarded `confirm-stop.py` can record
that exact completed STOP in host metadata without a second hardware write;
unknown failures remain sealed. Its unchanged pure qualifier passes the
previous actual saved pair and17 negative cases; no new live STOP is claimed.
The C OFF gate independently rechecks all prerequisites and ON completion.

Hardware preflight remains pending: exact kernel/notes, all3 SPMI PD
bindings/USB role providers, no conflicting owner, matched ADT/FDT layout,
exclusive resources and a qualifying PMP acknowledgement path. Existing
GRUB default5 selects the required kernel. Do not repeat a saved attempt,
use old warm/reset runners, restart, submit, detach/free or force unload.
Only a later verified trial can establish cessation or repeatable recovery;
triangle execution and the full Gravity GPU/Mesa/DCP desktop remain pending.
