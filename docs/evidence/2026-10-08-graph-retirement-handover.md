# shutdown ACKs verified; structural teardown/restart batch prepared

native boot8024c82a-5d11-49b4-ab30-c59ca344c3b2, actual source296d954,
exact receive13-retirement-candidate. regular7.1.13-m4rch-gpu-contract kernel
and promoted package/default boot unchanged. all3 PD controllers and USB roles
present before/after. subjective peripheral confirmation requested separately.

native shadowwalk passes for sparse owned pages. gate2 returns0.32 opcode16
controls consumed0/0/32 ->32/32/32, command bytes unchanged. both receive13/14
four-buffer sets entirely untouched/zero. no EHLC header, zero notifications
in30seconds,30 live RAM frames/one hash/no observer errors. this establishes
control processing with both experimental receive backings, not receive
readiness or rendering. main/header/power/status changes match earlier trials.

NEW: requested RTKit shutdown succeeds after graph publication:
101.689661s shutdown requested=1 root_sent=1;
101.691674s EP0 message0xb0000000000010 (AP quiesced ACK);
101.693658s EP0 message0x70000000000001 (IOP sleep ACK);
101.693670s AP_QUIESCED_ACK=1 IOP_SLEEP_ACK=1;
101.693680s ASC control0/status6e/stop_readback1.
DATA146908/146914 now1 (previous no-request runs0); raw observation only.
this is the standard local RTKit quiesce->restartable-sleep sequence, NOT OFF.
current candidate deliberately remains pinned even with ACKs. no unload/retry
on this boot; it lacks the qualified detach path prepared below.

user requests reducing repeated reboots. next graph-retirement-candidate adds
an explicit structural-only release gate; compiled/runner-enabled only with
the exact receive13/14+32-control recipe. same fixture bytes/pointers,69 owned
pages,100 device leaves/169 mappings and36 writable device pages; no new GPU
job, render command or device register permission. previous parser/control
models remain byte-for-byte applicable; teardown itself not hardware-tested.

release requires AP ACK, IOP ACK, ASC stop readback and empty receive FIFO.
then verify root link still equals OUR table descriptor, withdraw ONLY that
owned child entry, clean table and invalidate all169 GPU VAs, read back zero.
on any missing proof keep module/resources pinned. after successful detach,
backing remains allocated for post-stop snapshot and regular rmmod; no forced
unload/refcount editing. root_sent remains true; root_detached is the additional
acknowledged-release proof. snapshot sysfs is removed before pages are freed.
cleanup unmaps MMIO, returns runtime power reference and removes consumer.
this does not authorize retirement of a rendering GPU or outstanding jobs.

runner captures object/DATA evidence first, requires verified retirement log
and refcount0 before normal rmmod. then reads reserved tables and loader L2:
all71 published owned PAs must have no surviving table references; loader L2
must be empty; loader TEXT/DATA path must remain qualified. warm table baseline
must be unchanged; an initially all-zero cold table is allowed to become the
known loader path. two shadow/native allocation groups are correctly separated
by requiring the final complete sequential71-page group. module/consumer must
be gone, ASC mailbox MMIO claims gone, runtime suspend nonnegative. checks
reject incomplete allocation logs, lingering references and broken loader path.
20 mapping/serialization/lifecycle-proof tests pass; W=1 8-helper build succeeds
without warnings, all module/receipt hashes verified. preserved exact candidate.

--cycle 1/2/3 stores separate captures under the same boot. cycles2/3 require
previous successful unload/post-table verification and identical build receipt.
only those later cycles accept the exact retained loader root descriptor after
independently reading its empty L2. initial cycle retains fresh-boot guards.
ASC cold status guard remains6a; no speculative firmware DATA rewrite or warm
status bypass. a second startup may refuse6e or fail to replay HELLO. record
that as restart qualification failure, don't call shutdown ACKs a reset proof.
we can design the needed wake/reset path from observed state if necessary.

next source/candidate includes updated analyzer retirement fields and current-
cycle dmesg deltas, avoiding false success from an older cycle's log messages.
actual result:2026-10-08-receive13-native-result.json;
next recipe:2026-10-08-graph-retirement-candidate.json.
raw capture:asc-graph-init/boot-8024c82a-5d11-49b4-ab30-c59ca344c3b2.
next artifacts:out/gpu-gravity-contract/graph-retirement-candidate.
private implementation-derived numeric ABI work, NOT clean-room; no Apple
binary, firmware TEXT or complete disassembly in Git/return bundle.

ONE NORMAL LINUX REBOOT to load release-enabled version; no macOS required.
after r check fresh boot, USB and hashes; run:

    sudo -n python experiments/t6040-gpu/run-root-envelope.py out/gpu-gravity-contract --graph --run --cycle 1

inspect attempt.json and analyzer against exact graph-retirement-candidate.
only if graph_retirement_verified, unloaded and post_unload_verified all true,
run --cycle 2 then inspect; same gate before --cycle 3. stop on refusal/failure;
never force-unload pinned backing or rerun a recorded cycle. goal: demonstrate
three native publish->consume->quiesce->sleep->detach->unload cycles on one boot.
rebuild flags:--control-refresh --control-refresh-count 32 --receive14 --receive13
--retirement-probe --release-on-shutdown. no reboot issued; normal boot unchanged.
