# Thirty-second empty-channel trial returned; single refresh control prepared

Boot 9de00a9a-0023-4c3e-9354-a30d842750e2, kernel7.1.13-m4rch-gpu-contract,
source331c448. Gate1 shadow walk passed; gate2 returned0. All three USB role
providers and SPMI PD controllers bound BEFORE the GPU trial. User confirms
all desktop/input/USB/networking normal afterward. GRUB default1 and promoted
linux-m4rch-gpu-contract7.1.13-2 unchanged; backupUSBR001 entry3 retained.

Thirty-second observation: zero post-publication mailbox messages, no valid
EHLC crashlog (DATA+a0000 stillEF fill).29 live owned-RAM frames from0.106
through29.465seconds have identicalSHAec0c5e8be7170cc2f412075d51e6cc722c77f586b9fc5f8d2e5c22ca00483856.
Only initial main_header/power/status writes; every cursor and ring unchanged.
This shows no further observable owned-object progress during the window,
NOT full init, all16 AFR completion, stable firmware scheduling or rendering.
The absence of a fatal event is not an initialization-complete signal.

NEXT CANDIDATE BUILT: one initial opcode0x16 control record, index12; read0,
prefetch0,write1. No operands, FList, work command or extra doorbell. All twelve
work channels remain empty RAM surrogates; receive13..16 still unqualified.
Same47 owned pages/100 device leaves/147 total; no MMIO permission expansion.
The initial pending control matches Gravity g16_fw.rs/g16.rs setup. Matched
firmware jump table5284 entry18 plusbase3a3c dispatches4b1c; powerclass0;
handler4b1c..4b48 sets refresh flag and calls30a8, without reading operands.
Four private-global seeds follow root-parser2f2c8..2f300 (status_a is18e3f0,
not main_header). Offline actual-TEXT drain385c returns after316 instructions,
read/prefetch/write all1, and clears refresh flag. All accesses fit explicit
owned inputs. Model uses ZERO private state, disabled cache-helper config and
omitted pointer authentication: native cache/scheduling behavior unqualified.
This is a bounded control-processing experiment, not a render submission.
Evidence is implementation-derived and is NOT labelled clean room.

12 mapping/serialization tests,2 live-observer tests, offline work predicate
and control drain pass. W=1 eight-helper build passes without warnings.
Exact completed trial artifacts preserved atout/gpu-gravity-contract/long-channel-candidate;
next atout/gpu-gravity-contract/control-refresh-candidate. Evidence:
 docs/evidence/2026-10-08-long-channel-result.json
 docs/evidence/2026-10-08-control-refresh-model.json
 docs/evidence/2026-10-08-control-refresh-candidate.json
Raw current capture asc-graph-init/boot-9de00a9a-0023-4c3e-9354-a30d842750e2.

NORMAL LINUX REBOOT REQUIRED: current backing pinned/stopped. Never force
unload or republish on this boot. No macOS needed. After r, verify fresh boot,
USB baseline, matching module receipts and firmware contract, then execute
sudo -n python experiments/t6040-gpu/run-root-envelope.py out/gpu-gravity-contract --graph --run
Observe30sec/live RAM; inspect control consumer/prefetch for1, shared refresh
and fatal evidence. If no consumption, qualify actual worker/doorbell route
before adding further controls. Do not jump to0x20/FList or render jobs.
Rebuild command MUST include --control-refresh to reproduce this candidate;
without it the builder deliberately restores the prior empty fixture.

---

