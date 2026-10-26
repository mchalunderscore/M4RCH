# Separate paired GFX coordination trial

This future candidate adds the matched native PMP/PMC notifications around
the existing Gravity runtime-PM transition. The attempted power-off owner
and its saved boot339b9e8e evidence remain unchanged and pinned.

ON runs after physical ACTIVE and the existing cold ASC/FIFO checks, before
START or graph publication. It sets PMP request bit13, requires a matching
raw-valid ACK, then sets PMC voter bit2 on DCS/SOC/DISP_INT. OFF clears that
request and requires its ACK, clears the same voter bits, then performs the
existing single PM put and strict BUSY-clear observation. The native policy
values are an explicit experiment drawn from saved ADT; runtime Apple policy
and an equivalent hardware mode register remain unobserved.

The cold/resident runners compile exact hash-guarded copies of their frozen
power-off baselines with narrowly specified transformations. The new receipt
replaces the old scope key, so canonical new receipts are refused by the old
runners. New runners reject old and mixed receipts. Frozen legacy validators
were not changed and do not generally reject arbitrary hand-mixed receipts.

Before any sampler or cold load, the cold runner checks the installed kernel
identity and an exact 312-node Linux OF resource layout, including translation
cell widths, resource tuples, availability, compatibility and device type.
Changed or malformed metadata refuses before device access. Fresh ADT must
also match all12 native selection pins. The owner checks OF aliases and
exclusive PMP/PMC resource reservations. These checks do not prove that no
unregistered external writer exists; whole-word RMW is not atomic against
one. Any legitimate layout change must be inspected offline before updating
the guard; it never permits ignoring a conflicting resource.

ON admission pins the module before preparation, even on refusal. A startup
failure before firmware START retains the consumer, PM reference and acquired
resources without a graph interface. The cold runner saves the exact failed
boundary and admits no commands. Missing, malformed, contradictory or unknown
startup evidence also admits no graph reads, powered samplers, cleanup or
retry. Module absence after durable cold-load intent does not establish
retirement. Successful startup requires exact ON/owner records, a matching
loaded GNU module note, a positive lifetime reference, graph publication and
a retained resident/diagnostic marker.

After successful cold startup, use only `run-coordinate.py` for sample,
gfx-snapshot, one packet-free STOP and one terminal gfx-poweroff. A returned
STOP EAGAIN must be preserved; do not write STOP again or proceed without
qualified completion. The new `confirm-stop.py` reuses the exact previously
qualified metadata-only logic with this candidate's receipt/module guards;
it requires the next successful read-only START-clear/native-idle snapshot
and preserves the failed state/captures before recording known completion.
Unknown interruptions/errors remain sealed. The original boot-specific
helper refuses this candidate. OFF coordination failure retains the still-held PM
reference; eligible OFF consumes it exactly once. No rollback, compensation,
reset, warm INIT/START, submission, retirement, unload or automatic reboot is
provided. Post-OFF observations remain PMGR/software/retained DRAM only.

`finalize-candidate.py` binds the separately built owner to the actual-core,
adapter and wrapper qualifications. It records the new receipt, sources,
unchanged helpers/graph/kernel bindings and build imports. It performs no
hardware action. Preparation and tests establish implementation readiness,
not hardware teardown, DMA/UAT/cache drain, repeatable restart or rendering.

Never load this candidate on boot339b9e8e. A fresh normal user boot is required
because that boot's prior owner and published backing cannot be safely
replaced. Existing GRUB default5 selects the same qualified kernel; no new
kernel installation or default change is required. Root must recheck kernel,
USB/SPMI/role-provider identity and absence of a conflicting owner, then use
the distinct cold runner with `--graph --run`. Do not repeat an existing
attempt or substitute the historical reset/warm runners.
