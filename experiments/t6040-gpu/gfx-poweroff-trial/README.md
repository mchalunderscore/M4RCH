# Distinct retained GFX power-off trial

The native-command reset completed its writes on boot a1f61d61, including
RESET31 observed set then clear and AUTO restored. Firmware-owned shared
fields still changed about100 seconds after packet-free STOP. Repeatable
recovery, physical cessation and safe backing release remain unproved.

This separate candidate tests one ordinary runtime-PM suspend after STOP,
with every allocation, mapping, consumer and the module retained. It uses the
installed `7.1.13-m4rch-gpu-native-reset` kernel's existing snapshot API;
it has no reset pulse, restart, triangle publication or backing release.
Read `gfx-poweroff-scope/README.md` for the exact C admission and observations.

`prepare-trial.py` verifies the frozen native candidate, kernel, source and
wrapper qualifications, creates an exclusive new directory, changes only
the owner's scope header, recovery dispatch, feature flag and log message,
then compiles that owner with W=1. The other seven helpers, graph fixture and
triangle backing remain byte-identical. Source and artifacts of the current
resident owner remain unchanged.

`derive-runners.py` records the exact baseline scripts and transformations.
The generated `run-root-poweroff.py` permits only the new contract and graph
startup. Mandatory gate1 shadow precedes gate2 with observe_ms5000 and
resident_session1; old reset receipts, arena mode, numbered cycles and warm
restart are rejected. `run-poweroff.py` binds the original retained session,
kernel, artifacts, source, loaded module GNU build note and firmware TEXT.
Its only commands are sample, gfx-snapshot, stop and gfx-poweroff. A confirmed
STOP precedes the sole OFF; durable intent is recorded before opening sysfs.
An uncertain or interrupted OFF never permits another attempt. After OFF
intent only sample/gfx-snapshot remain available, using existing DRAM/journal
captures and the driver's PMGR snapshot. Unknown STOP also closes mutation.

Run `test-runners.py` for actual Python admission and simulated durable sysfs
intent tests. `wrapper-qualification.json` records84 passing cases and exact
source hashes. The qualification does not access hardware.

The prepared candidate is `out/gfx-poweroff-scope/candidate`; its
`power-off-preparation.json` binds the build and both qualifications.
It has NOT been loaded or used for hardware power-off. It requires a new
user boot because the current old owner is pinned with a consumed gate.
The installed kernel and GRUB default5 already match; no kernel installation
or default change is needed.

After independently validating a fresh boot, root alone may establish the
new owner using `run-root-poweroff.py CANDIDATE --graph --run`, capture a
baseline, issue typed STOP, then at most one typed gfx-poweroff. Require the
driver-owned independent domain/raw-state observation: runtime suspend
return0 can occur while the provider remains on. Every outcome keeps backing
pinned and permits only PMGR/DRAM evidence afterwards. OFF plus stable DRAM
still does not authorize restart, unmapping, freeing or successful-rendering
claims. Never run the future owner against the current retained session.
