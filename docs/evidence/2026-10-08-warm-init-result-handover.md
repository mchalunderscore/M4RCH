# cold graph retirement reproduced; INIT wake fails, do not repeat

bootfa78dd48-b214-46fc-8786-cae63897ad78, source1f1eeae, exact warm-init-candidate.
normal7.1.13-m4rch-gpu-contract/package/default unchanged. all3 PD controllers
bound before/after, all3 USB roles before trial. user confirms everything normal after both trials.

cold cycle1 succeeds end-to-end again:32opcode16 controls consumed32/32/32,
command bytes unchanged, no EHLC or mailbox notification, zero receive13/14
buffers. AP quiesce/IOP sleep ACKs, stopped0/6e, owned-root detach/TLB invalidation,
post-stop snapshot, normal unload. all71 owned PAs unreferenced, loader L2 zero,
loader TEXT/DATA mappings qualified, module/consumer absent, power suspend0,
MMIO claims released. post_unload_verified true directly, no report correction
needed this boot. this independently confirms structural/no-job teardown.
not a rendering DMA retirement proof or restartable-session success.

warm START+IOP INIT0x220: entry0/6e, standard INIT sent, four-second poll returns
no messages/HELLO/map. no warm root sent. final control0/status48, stop_readback0.
probe retains power/MMIO/refcount1; published backing from cold cycle1 already
freed. warm graph buffers never allocated/published. EHLC absent in post-capture.
REBOOT REQUIRED. never force-remove, repeat publication, restart48 or unmap this
retained failed-start probe. don't falsely report successful stop/reusable loop.

IMPORTANT HISTORY LINK: this matches 2026-10-07-gravity-gpu-explicit-wake.json.
2026-10-07-gravity-gpu-managed-wake.json also produced no messages/status48 with
START unchanged and GFX power continuously held. therefore toggling START or
releasing power is NOT the sole explanation; retaining them and repeating INIT
is not a new justified test. earlier handover already said no blind wake variants.
the latest INIT trial adds a different prerequisite (published graph successfully
retired), but INIT should not have been described as an undiscovered missing step.
recorded history now explicitly linked to prevent this repetition.

current result:docs/evidence/2026-10-08-warm-init-native-result.json.
raw captures:asc-graph-init/boot-fa78dd48-b214-46fc-8786-cae63897ad78/
cycle-1 and warm-restart-1. exact module receipt/fixtures remain saved under
warm-init-candidate. no next hardware wake candidate prepared or queued.

next: clear current failed probe with a normal Linux reboot, no macOS needed.
after r verify fresh boot/peripherals/hashes. don't rerun warm INIT or another
identical cold cycle merely for reassurance. cold release is now independently
reproduced; use it when a new graph/command batch needs a bounded lifecycle.
resume GPU ABI/init progress and audit the actual reset/recovery contract offline
from matched AGX353.14/25G83 and available loader/kernel sources. relevant private
symbol sites:bootFirmware89ca7cc, stopFirmware89ca784,
stopFirmwareForRecoveryInspection89ca56c, resetFirmwareForRecovery89d1650.
identify service boundaries/register prerequisites, source of reset vector,
firmware DATA/table restoration and power-domain ordering before a targeted
reset experiment. don't invent reset bits, rewrite firmware DATA, cycle shared
power domains or bypass stopped48. send a concrete macOS evidence request only
if runtime reset/loader behavior cannot be qualified locally.

user goal remains reducing reboots: successful release is achieved; firmware
restart is unresolved. an alternative is a persistent powered session for many
controlled batches, but it needs proven submission/completion/fixture lifetime,
not treating a sleep ACK as permission to resume through freed pointers.
rendering work still needs correct return-channel contents/initialization,
remaining shared objects, work queues/job ABI and completion handling. static
private pointer/extent facts do not supply initialized objects automatically.
private implementation-derived work, NOT clean-room; no Apple binary, firmware
TEXT or full disassembly committed/bundled. no reboot issued; normal boot unchanged.
