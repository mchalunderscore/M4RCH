# structural GPU release verified; warm wake needs RTKit INIT

boot8fc6f0d0-c9bf-4475-89ed-8118352ea6bf. first native candidate from4e503b6,
graph-retirement-candidate. ordinary7.1.13-m4rch-gpu-contract/default/package
unchanged. user confirms everything normal after cold shutdown/unload; all3
PD controllers remain bound after later warm experiment.

cycle1:32 opcode16 records consumed32/32/32; no EHLC/notifications; both receive
sets untouched.29 live owned snapshots/one hash/no errors. AP quiesce and IOP
sleep ACKs arrive again; ASC stop0/6e. own child descriptor verified, removed,
169VAs invalidated, backing retained for snapshot then normal rmmod succeeds.
71 owned physical pages have no surviving reserved-table references, loader
L2 empty, module/consumer absent, MMIO reservations released, runtime suspend0.
this is native structural/no-job resource release, NOT rendering DMA retirement.

post-proof initially false because checker required firmware GPU L0 entry2
retained as200105fff744cb; actual entry isZERO. TEXT/DATA paths remain exactly
qualified (L0/L1 pointers and TEXT10000be4000/DATA10001d44000). initially cold
reserved tables were zero and firmware populated them during startup. corrected
checker accepts only zero GPU root or exact known loader descriptor; warm
baseline permits ONLY that entry's removal, all other bytes unchanged.
original attempt-initial.json preserved; attempt.json includes offline
revalidation/checker hash/initial-report hash, hardware_action=false.
no remaining owned references; don't misreport this as retained backing.
20 tests pass including cleared-root positive cases, wrong-root negative cases,
broken TEXT path and lingering physical references. no forced unload used.

cycle2: new allocation shadowwalk passes and frees; actual startup refuses
EBUSY before START, no root published or module retained. no implicit retry.
then explicit warm-restart-candidate experiment requires this boot's verified
prior release and same fixture/kernel hashes, permits only stopped6e alongside
usual6a. observed entry0/6e; START raised, bounded4second poll produces NO
HELLO, reply or endpoint map. no new graph publication/owned native graph.
ASC stops0/6e; failed-start probe pins power/MMIO and refcount1. reboot now
required before another trial, never force-unload. buffers from cycle1 DID free.

local kernel RTKit wake supplies concrete missing step:
linux/drivers/soc/apple/rtkit.c apple_rtkit_wake sends management type6 IOP
power stateINIT0x220, then apple_rtkit_boot waits for endpoint map/IOP power
completion. OFF is not requested. current warm replay did not send INIT.
next warm-init-candidate adds exactly that request after START, only in explicit
warm mode. otherwise cold initialization identical. same69 owned pages,100
unchanged device leaves/169maps/36 writable pages and32controls; no render jobs
or firmware DATA rewrite. HELLO/map negotiation still bounded4seconds, matched
reserved crash buffer protocol afterward; shutdown/release checks unchanged.
TX full or incomplete handshake retains probe and stops core. native INIT wake
unverified; real message ordering may require further RTKit state handling.
W=1 helper build passes without warnings; all hashes verified. exact artifacts
saved separately:graph-retirement-candidate, warm-restart-candidate,
warm-init-candidate. next runner retains original release proof/checksum data.

raw root:asc-graph-init/boot-8fc6f0d0-c9bf-4475-89ed-8118352ea6bf/
cycle-1,cycle-2,warm-restart-1.
evidence:2026-10-08-graph-retirement-native-result.json,
2026-10-08-warm-restart-native-result.json,2026-10-08-warm-init-candidate.json.
implementation-derived private ABI research, NOT clean-room. no Apple binary,
firmware TEXT or full disassembly committed/bundled.

NORMAL LINUX REBOOT required because failed warm replay probe is retained.
no macOS needed. after r verify fresh kernel/candidate/USB then:

    sudo -n python experiments/t6040-gpu/run-root-envelope.py out/gpu-gravity-contract --graph --run --cycle 1

analyze exact warm-init-candidate and check graph_retirement_verified,
unloaded,post_unload_verified all true. then on SAME boot:

    sudo -n python experiments/t6040-gpu/run-root-envelope.py out/gpu-gravity-contract --graph --run --warm-restart-from out/gpu-gravity-contract/asc-graph-init/boot-BOOTID/cycle-1

replace BOOTID with actual boot ID. inspect HELLO/map/IOP state/crashlog/root
consumption and shutdown/unload. warm root entry may be zero; retained exact
entry acceptance requires separate empty L2 capture. no repeated recorded
attempt, no DATA restoration or unqualified power reset. goal is restartable
session without reboot, not assumed achieved because unload worked.
rebuild:--control-refresh --control-refresh-count 32 --receive14 --receive13
--retirement-probe --release-on-shutdown. boot package/default unchanged;
no reboot issued. current failed warm probe retains no published owned graph.
