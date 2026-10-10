# Retained Running cycle: EP1 message before host reply

Boot `df540c1c-5ec4-44f5-894c-37be6c2f3527` completed the distinct version 10
trial once. Firmware restarted after physical OFF, completed HELLO and endpoint
mapping, and sent the exact Running notification. The owned HOST B20 publication
path followed, but the next removed message was EP1 type1 rather than the required
EP0 B20 reply. The strict parser returned `-71/host-on-reply-unqualified` before
any second202 request, CPU stop, paired OFF or PM put. This was not a host-reply
timeout or a failed second shutdown ACK. Pending mailbox contents remain unknown.

Fresh preflight passed with the expected kernel, ten artifacts, twenty sources
and all three USB/PD bindings. The cold owner published its no-work root and
retained all 174 pages; initial recovery completed zero of two cycles. Its exact
module GNU identity matched the frozen file with refcount 1. The first shutdown
drained nine qualified EP32 messages and received its own ACK after eight polls.
RX-empty/idle, checked CPU clears, paired OFF and one PM put reached strict
physical `0x0f000300`, held/usage zero and suspended/error zero. The returned raw
proof bound seven inputs. This is the fifth first shutdown on distinct fresh boots.

The second PM reference restored ACTIVE and a separate E2 paired ON completed;
native zero-status wait bypass is not an ACK. Fresh preON STATUS6c and postON6d
qualified. One START write read back CTRL10 at `312.356019`. Autonomous HELLO12
and both exact map ACKs completed by `312.359397`. Exact EP0 boot
`0x0070000000000020` arrived at `312.360525`, before HOST intent `312.360544`.
The later write flag and the unconditional selected source path establish the
owned HOST `0x00b0000000000020` publication path; no independent TX readback was
captured. The next frame at `312.361662` was EP1 `0x0010110001de4000`, metadata
`0x0010450000000001`. Its descriptor format yields address `0x10001de4000` and
extent `0x1000`; that format alone does not establish a harmless buffer request.
Cold startup used the same address with extent `0x8000` and echoed it before its
Running/HOST exchange. Native existing-buffer crash semantics require separate
investigation. No EP1 echo or further control was sent on this trial.

All six state rows were complete in the immediate return and final capture,
with maximum 354 bytes including prefix and newline. Later admitted diagnostics
read fresh physical ACTIVE `0x1f0003ff` at `419.944917`, then held1/usage1,
runtime_status0/error0 at `419.944921`. ASC fields were deliberately not sampled;
cached CTRL10/STATUS6e are earlier host-guard operands. Historical first-OFF and
host-stopped flags do not prove the current epoch stopped.

The full original receive journal remained byte-identical across first OFF,
cycle and later snapshots: used51217, flags0, doorbells9. The five E2 frames were
recorded separately. Object and owned DRAM changed after restart, then both
later copies matched their cycle copies. Non-atomic snapshots establish neither
global cessation nor writer identity or joined DMA retirement.

The loaded version 10 owner remains pinned and sealed with both intents consumed
and its second reference held. Only admitted sample/snapshot diagnostics remain;
no control retry, mailbox drain, new GPU owner, root/context/work publication,
memory release or unload is permitted. No build or hardware subprocess is pending.
Second shutdown, a full management roundtrip, application rejoin and rendered
pixels remain unproved.

The companion JSON binds 64 inputs, SHA-256
`1517e67f0699e111c44a41a3d739236d65e50f6edf7d7abbb4a5e194f55e18b6`.
Candidate owner `c0dd4c7f939e328b83ede890216df099b1935a9af3b8e0bd3a7593213995a037`,
receipt `32b2ff0c647eae38a4f74486dc4f85793fdbfe478d60ab96555eb290d4564c65`,
preparation `a2237389fa172c4f319c482df7ab9b58bbd551339ce690c8789ab2ae90a83303`.
No kernel or GRUB configuration changed.
