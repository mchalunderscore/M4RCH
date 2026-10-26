# receive14 native result; receive13 and restartable-shutdown trial ready

current boot5a5d8669-ec19-4382-83f7-1bddb01b31bc, actual trial from commit8e70b58
and preserved receive14-candidate. normal7.1.13-m4rch-gpu-contract kernel,
promoted package/default boot unchanged. all3 PD controllers bound before/after,
all3 role providers present. user confirms desktop/input/USB/networking normal.

32 opcode16 controls consumed again:0/0/32 ->32/32/32, record bytes unchanged.
no EHLC header, zero mailbox notifications in30seconds;30 live owned-buffer
frames, one unique hash, no observer errors. all four receive14 buffers remain
zero, no changed byte. backing accepted far enough to process these controls;
not proof receive readiness, event generation, full initialization or rendering.
source receipt and original fixture checked against the actual capture.

important retirement finding: published-graph probe SKIPS AP quiesce/IOP sleep,
rather than attempting and failing them. old AP_QUIESCED_ACK=0/IOP_SLEEP_ACK=0
means NOT REQUESTED after root_sent. ASC stop readback is0/6e. current module
has no restart/request interface, remains pinned, must not force-unload.

user requests avoiding repeated reboots. next candidate requests the local
kernel RTKit shutdown sequence after the usual observation: AP request/reply
0xb state0x10 (quiesced), then IOP request6/reply7 state1 (restartable sleep).
2second bound per request, existing bounded mailbox drain. no OFF request
(which kernel documents as potentially requiring full SoC reset). new readonly
request_shutdown parameter enabled only by prepared receipt/runner. this is
an ACK experiment, NOT permission to free buffers: root_sent still unconditionally
prevents retirement/release even if both replies arrive. ordinary stop readback
and receive FIFO state alone are insufficient. compare runtime with local
linux/drivers/soc/apple/rtkit.c apple_rtkit_shutdown and g16.rs Bootstrap Drop.

if both ACKs arrive, next work is a lifecycle trial: validate GPU activity has
ceased, snapshot before teardown, withdraw ONLY our owned root child entry,
clean/invalidate its VAs, release owned mappings/power, then prove a fresh
session can initialize using a qualified reset/restart and firmware DATA/table
state. all buffers stay pinned on incomplete shutdown. successful shutdown
alone doesn't prove fresh boot state or rendering-engine DMA retirement.
never directly clear the refcount or merely remove the root_sent guard.
if ACKs timeout, decode response/firmware scheduling state and audit mailbox
protocol before trying a reset. don't cycle broad/shared power domains blindly.

next batch also adds receive13 four-buffer backing, alongside receive14.
correct prior handover typo: receive13 state_b allocation is1b0 (432) bytes,
not30 (48). exact pinned allocation descriptor construction and eight added
mapping-site checks tie CPU900/920/908/928 to main+1c0/1c8/1d0/1d8.
receive13 extents30/4800/1b0/28800; receive14 unchanged30/9000/30/4800.
zero contents remain experimental; no cursor role/cache policy/event decoding
or complete initialization assertion. receive15/16 still untouched.

69 owned RAM pages,100 unchanged device leaves,169 mappings; same36 writable
device pages. receive13 ring needs11 contiguous GPU pages: logical backing
starts at page58, GPU VAfffffc2000224000, after primary device pages ending
there. new explicit owned_page_vas separates flat observation backing offsets
from GPU addresses, preserves root and all old pointers. no collisions, split
objects or cross-L2 mapping. C mapper rejects occupied L2 slots; offline
validator checks spans, aliases, root, object coverage and encoded pointers.
models map actual GPU page VAs rather than assuming a flat virtual arena.

18 mapping/serialization/bounds tests pass, including collisions, duplicate
pages, broken contiguous spans and changed encoded pointers. exact candidate
root-parser model returns after2223 instructions;32-control model drains to
32/32/32 after7508 instructions. models still omit pointer authentication,
substitute RTKit receive and seed private state; not hardware proof. W=1
8-helper build succeeds without warnings; all artifact hashes verified.

current native capture:asc-graph-init/boot-5a5d8669-ec19-4382-83f7-1bddb01b31bc.
evidence:2026-10-08-receive14-native-result.json,
2026-10-08-private-receive13-layout.json,
2026-10-08-receive13-retirement-candidate.json.
next exact artifacts:out/gpu-gravity-contract/receive13-retirement-candidate.
no Apple binary, TEXT or full disassembly committed/bundled; implementation-
derived private numeric ABI work, NOT clean-room.

ONE NORMAL LINUX REBOOT required to load this updated probe. no macOS needed.
after r verify fresh boot/USB/module hashes, then run once:

    sudo -n python experiments/t6040-gpu/run-root-envelope.py out/gpu-gravity-contract --graph --run

analyze exact receive13-retirement-candidate. check both receive buffer sets,
32controls, notifications, EHLC and shutdown request/reply logs. even if ACKs
succeed this candidate still pins backing; use evidence to design reusable
lifecycle next, do not repeat publication on the same boot.
rebuild:--control-refresh --control-refresh-count 32 --receive14 --receive13 --retirement-probe.
no reboot issued. package/default boot untouched.
