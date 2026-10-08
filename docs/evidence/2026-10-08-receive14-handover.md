# 32 native refresh commands consumed; receive14 experiment prepared

boot633fe932-1e6b-42df-974c-fc4daa0f8670, trial sourced36b61f and exact
refresh-batch-candidate artifacts. regular7.1.13-m4rch-gpu-contract kernel,
promoted package7.1.13-2 and default GRUB entry unchanged. user confirms all
desktop/input/USB/networking behavior normal after the trial.

USB baseline: left PD0-0c failed ENODEV SN201202x initialization at4.667977s,
before GPU activity. saved original dmesg; targeted normal SPMI reprobe of only
unbound0-0c succeeds. all3 PD controllers bound before/after GPU. all3 USB role
providers remain present. this readiness race is separate from the GPU trial;
don't unbind working controllers or call it a missing kernel promotion.

gate1 shadowwalk passes; gate2 returns0. all32 opcode16 refresh records are
consumed, cursors0/0/32 ->32/32/32, record bytes unchanged. no EHLC header and
zero mailbox notifications in30seconds.29 live owned-RAM snapshots, one unique
hash, no observer errors. consumption precedes the first snapshot. no native
render/compute jobs, receive-channel readiness, full startup or acceleration
claim. backing remains pinned/stopped with no retirement acknowledgements.

broader private AGX353.14/25G83 audit: offline Unicorn executes only reviewed
straight-line CPU allocation-descriptor construction89ab98c..89abbb8, using
actual file-backed constants/code and zero fake host/stack.27 descriptors
recovered, no service/allocation/hardware calls. nine additional pinned mapping
sites connect main+1e0..1f8 to CPU fields910/930/918/938; allocation extents
30/9000/30/4800. main+1c0..1d8 instead uses900/920/908/928 with extents
30/4800/30/28800. main+200's CPU880 buffer is79800bytes, not a tiny cursor.
these extents distinguish receive records from control's three RAM cursors;
do not copy our empty work/control layout onto receive channels. internal
content, metadata roles, cache policy and notification production unqualified.
numeric observations only; private binary/disassembly not in Git/bundle.

next native candidate populates descriptor14 with four independent zero-owned
buffers of the static extents.7 additional RAM pages:54 owned pages,100 device
leaves,154 mappings. same36 writable device pages, no device address/permission
changes. unchanged32 opcode16 controls, no work jobs/extra doorbells. main+1e0
gets four pointers;13/15/16 remain unchanged. all four new reserved extents stay
below the first device mapping. zeros are explicit experimental contents, not
validated complete initialization. this tests acceptance and passive writes,
not a guaranteed startup response or active host event draining.

16 mapping/serialization/bounds/receive-extent tests pass. full fixture root
parser model returns after2223 instructions; bounded control drain returns
32/32/32 after7508 instructions. RTKit receive substitution, pointer-auth
omission and zero/private-state model assumptions remain explicit. no model
claims event publication. W=1 eight-helper build passes without warnings;
all module/receipt hashes match. artifacts:out/gpu-gravity-contract/receive14-candidate.
analyzer additionally reports raw receive buffer changes and words, without
inferring cursor roles or decoding events.

evidence:2026-10-08-refresh32-native-result.json,
2026-10-08-private-receive-layout.json,2026-10-08-receive14-candidate.json.
raw capture:asc-graph-init/boot-633fe932-1e6b-42df-974c-fc4daa0f8670.
USB pre-reprobe log preserved separately with the next candidate/bundle.
implementation-derived private work, NOT clean-room.

NORMAL LINUX REBOOT required before another publication; no macOS needed.
never force-unload or republish on this boot. after r verify fresh boot,
USB baseline and matching modules, then run:

    sudo -n python experiments/t6040-gpu/run-root-envelope.py out/gpu-gravity-contract --graph --run

analyze against receive14-candidate, not refresh-batch-candidate. check native
control consumption, all four receive buffers, any notification/crash and
peripherals. rebuild uses --control-refresh --control-refresh-count 32 --receive14.
next independent work: trace event producer/host callbacks and exact buffer
initialization, then qualify logging/mapping-notification backing. adding all
larger buffers will need a packing plan that avoids our current device VA
window; don't allocate through it. rendering still needs real channel state,
command/job ABI, coherency/lifetime and interrupt completion. no reboot issued.
