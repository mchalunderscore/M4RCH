# Actual bootstrap power20 and second-cycle ordering

The second-cycle0x0070000000000020 frame has an exact cold-bootstrap precedent.
It is a boot power/ON notification, not a qualified shutdown ACK. The first
three full RX message/metadata pairs in the new cycle exactly equal the cold
HELLO12 and two endpoint-map pairs. Its fourth RX pair is EP0/type7/low20.
[Raw chronology and pins](2026-10-09-gfx-native-idle-cycle-boot-power20-protocol-review.json)
bind actual boot54e2, the frozen version9 owner, both complete logs and journal
snapshots, and the separate matched native review.

| Event | Cold time | Second-cycle time |
|---|---:|---:|
| HELLO12 RX |72.286511|166.710147|
| HELLO_REPLY TX |72.286518|166.710151|
| Map0 RX / ACK TX |72.288541 /72.288550|166.711259 /166.711265|
| Final map1 RX / ACK TX |72.290502 /72.290511|166.712381 /166.712385|
| New EP1 START |72.290516|absent|
| EP1 reserved DATA offer / echo |72.292533 /72.292549|absent|
| Own second202 intent |absent|166.712397|
| EP0/type7/low20 RX |72.294499|166.713511|
| Own HOST typeB/state20 reply RX |72.296518|absent|
| Joined context install |72.298440|absent|
| EP32/33 START |72.298450 /72.298454|absent|
| EP32 root publication |72.298642|absent|

The cold source starts system endpoint1, validates and echoes a firmware-owned
reserved DATA offer, and waits for that offer plus IOP power20. It then sends
one HOST0x00b0000000000020 and waits for the exact EP0/typeB/state20 reply.
Only after both stages does it prepare the live root/context, start EP32/33 and
publish the EP32 root. The HOST request is derived from the frozen executed
source path; its reply is directly logged. The cold warm_restart flag is0;
no INIT220 is sent. The legacy 'requesting ASC core stop' line between map and
EP1 is prose at that call site, not an observed CPU-stop operation.

The second sequence sends no new EP1 START/offer echo, HOST B20 handshake,
application START, root or INIT220. It issues second202 immediately after the
final map ACK, before consuming power20. Displayed log times put power20 about
1.126ms after the final map ACK and after the202 intent; cold power20 follows
its final map ACK by about3.988ms. These are sampled log intervals, not bus
latency bounds. No actual type7/low1-or2 shutdown ACK is accepted. The frozen
predicate properly refuses power20 with EPROTO; CPU STOP, paired OFF and PM put
remain unattempted and the second reference remains held. This does not prove
whether a valid shutdown reply might later have arrived.

The matched native type7 handler maps low20 to host IOP8 Running. The prior
generic claim that normal validation always expects6 needs correction:
_iopValidate expects8 by default; remote-only or automatic-rail-gating flags
select6 Ready. Native state7 is Pwr Dwn. These host software states are distinct
from ASC STATUS48 hardware6c/6d. Matched native ON notification also supports
an own HOST B20/state20 request and fresh state20 reply, with skip/already-remote
conditions. Runtime class/flag provenance remains unbound, so this is a bounded
next ordering hypothesis, not a universal claim that every native path must
perform both exchanges.

The50,410-record cold receive journal contains application RX13/RX14 ring data;
it does not store these EP0 bootstrap mailbox pairs. Its receive service starts
only at root publication. The new four pairs live in a separate16-entry local
host protocol journal and are captured here through complete RX log rows plus
final protocol_records=4, rather than a binary snapshot of that local array.
The saved application journal is separately decoded and pinned. Retained EP1
state may survive; receiving20 without a new EP1 START does not prove endpoint
independence or full endpoint/DATA/context restoration.

The useful missing stages are separate boot Running observation and, subject
to the native conditions, an own HOST ON handshake before own202. Neither20
frame may become a shutdown ACK, and neither proves application rejoin,
physical OFF, execution, rendering, DMA retirement or backing release. This
review edits no frozen source/evidence and performs no live read or command.
