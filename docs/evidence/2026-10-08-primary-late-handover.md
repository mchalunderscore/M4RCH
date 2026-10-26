# Primary batch advances to late startup; next bounded segment prepared

Bootbf7ba896-2325-4cc6-9d3a-fe8aa338a37e, native source4ea2cc8. Regular
GPUC001 kernel7.1.13-m4rch-gpu-contract, package7.1.13-2, default1 and USBR001
backupentry3 unchanged. All3 USB role providers and PD controllers bound
before/after; user Everything normal after larger GPU batch. No macOS needed.

PREPUBLICATION CORRECTION: previous five-page candidate omitted updates to
Python/native allowlists. First runner rejection occurred before intent; gate1
shadow allocation then rejected/freed before ASC activity. Preserved partial
intent/log in capture gate1-blocked-intent.json and prepublication-guard-failure.json.
Both guards corrected; new13th consistency test compares qualified write set
with runtime/native allowlists. No weakening of once-per-publication protection:
only proven prepublication failure intent archived before actual cold attempt.

Actual corrected gate1 shadowwalk passes and gate2 returns0. New2576-byte,
footer-valid crashlog, oneEP1 fatal notification. PCaac8, FARfffffc2000201710,
ESR9600004f: STRX19,[X8,#1710], nativeX80xfffffc2000200000/X190. Physical
288001710 lies on read-only primarypage288000000. Firmware advanced from8050
to this later initialization point after five-page grant. NOT proof all37
modeled writes ran or of completed startup. Control read/prefetch/write still
[0,0,1], unconsumed.18 live RAM snapshots0.106..29.093sec, no observererrors,
one unique framehash after initial object writes. Linux/peripherals normal.

NEXT: matched-TEXT continuation aac8..b4a4 (before state-query helper), plus
reviewed helper2a7c8..2aa14, reaches boundary after222 instructions and23
modeled register writes across six primary pages. Five alreadyRW; only
288000000 is newlyRW. All six identified pages covered together; this is not
an isolated1710-instruction trial. Model uses native Crg8 registers with explicit
zero private DATA/register RAM, cached primary/main globals seeded and omitted
authentication. No hardware behavior/state-query/whole startup completion claim.
Later b4a4 state query and subsequent paths unmodeled; unknown code/memory aborts.

Same100 device leaves/47 owned pages/147total, now35 devicepagesRW. No new
mapping addresses; graph bytes identical. One initial opcode16,producer1;
work0..11 remain empty RAM surrogates, receive13..16 unqualified. No extra
commands/FList/doorbell.13 mapping/serialization/allowlist tests pass, late
continuation passes, W=1 eight-helper build passes without warnings. Exact
actualtrial primary-guards-candidate preserved; next primary-late-candidate.

Spec comparison: matching firmware supports rootc8/interface0c8aa322039604c0,
17x20 main descriptors, shared pointers254+, power471 and RegionC assertion
e51. Two-cluster voltage geometry agrees with capturedADT. Uploaded J616s spec
uses20cores masks3ff/3ff; our J614s16cores3db/3db expected variant difference.
Several shared-object extents are still minimum/provisional, not fully proven.
Render/compute/channel-state/queue-completion sections are NOT hardware tested;
current main descriptor cursors are not that separate channel-state structure.
No major contradiction found in audited init subset; spec is useful but not a
fully validated hardware contract. MMIO mapping/startup details are added evidence.

Evidence docs/evidence/2026-10-08-primary-startup-result.json,
 primary-startup-crash.json, primary-late-model.json, primary-late-candidate.json.
Raw capture asc-graph-init/boot-bf7ba896-2325-4cc6-9d3a-fe8aa338a37e.
Evidence implementation-derived; preserve provenance, no clean-room label.

NORMAL LINUX REBOOT required: current backing pinned/stopped. Never force
unload or republish on this boot. After r verify fresh boot/USB/receipt/TEXT,
then sudo -n python experiments/t6040-gpu/run-root-envelope.py out/gpu-gravity-contract --graph --run
Same30-second mailbox/live-owned-RAM capture. Inspect panic, controlconsumer
and shared state; ask physical input/USB confirmation. Batch next qualified
segment if further fault. Reproduce with build-root-envelope.py out/gpu-gravity-contract --control-refresh.

---
