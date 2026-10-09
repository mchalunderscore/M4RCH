# Retained firmware restart succeeded; shutdown hit a boot notification

Boot `54e21e8f-b6f8-42cc-a5e5-e3f42831b870` proved a limited same-owner firmware
transport restart after strict physical OFF. The second paired ON completed,
one fresh START write read back with CTRL44=10, and the firmware autonomously
sent HELLO12 plus both exact endpoint maps. The host replied to all three.
The subsequent second shutdown refused EP0 type7/low20 before CPU stop or OFF.
This is progress beyond the prior status guard, not a completed management
roundtrip, application restart or rendered triangle.

Owner SHA `6c37c9f63419364fade9d1e402bce554b25c9cb5b855e514fb017de193d9f56b`,
receipt `027b5dbf79e2cceecdb82823c5daba4bc5b7cdacb05cb7228b2b11cb5d6deeea`,
and preparation `2a8cc03ff760702d2d052fc8f047527cafa54a252e25d67e2aef664036b31d80`
match the selected version9 candidate. Fresh kernel/artifact/source/USB/PD/role/
resource preflight passed. The pure loaded GNU note matches, refcount1.
The cold no-work trial returned zero, qualified four commands and retained174
pages; initial recovery completed0/2 and no work was submitted.

The first shutdown again qualified its exact returned seven-input raw proof:
eight admitted EP32 frames, own202, native low1 ACK after three polls, fresh
RXempty/nativeidle/CPUclears10/20 readbacks0/0, paired OFF and one PM put.
The first physical word was strict0f000300/BUSY0/domainOFF with held0/usage0/
suspended/error0. This is the fourth first shutdown on separate fresh boots.

| Retained stage | Actual saved result |
| --- | --- |
| One new second PM reference | Return0; held1/usage1/ACTIVE/error0; physical1f0003ff |
| Fresh pre-ON / post-ON | CTRL0, STATUS6c then6d, valid empty RX and available TX |
| Separate paired ON | Full REQ2000, three vote4 readbacks; native STATUS0 wait bypass, no ACK claimed |
| One fresh START / readback | CTRL10; START-return at166.709031 |
| Autonomous transport | HELLO12 + base0/bitmap3 then base1/bitmap3/last; replies at166.710151,166.711265,166.712385 |
| Second own202 path | Reached after final map ACK; intent at166.712397 |
| Next removed frame | EP0/type7 `0x0070000000000020` at166.713511; unqualified for shutdown |
| Final cycle return | `-71`, second-ack-unqualified; second CPUstop/OFF/put all0 |
| Later typed diagnostic | Fresh physicalACTIVE1f0003ff and clean held1 accounting; ASC/MMIO skipped |

The `0x20` frame arrived1.126ms after final map ACK. Receipt chronology alone
does not make it a causal ACK of the second202. The native/cold protocol reviews
are separate evidence; this outcome does not relabel it as a shutdown ACK.
START intent alone is also insufficient: the actual START-return and complete
fresh protocol exchange provide the limited transport-restart proof.

Four second-epoch frames were recorded in a separate local protocol journal.
The original full receive journal stayed byte-identical at51176 records,
status0/doorbells8 across first OFF, cycle and later. The raw object images
differ at each sample; the owned cycle/later images match each other but differ
from first OFF. No global cessation or writer identity is established. Snapshots
are non-atomic. The later fresh PMGR/accounting at239.112279/239.112285 differs
in scope from cached CTRL10/STATUS6c/FIFO fields from the second protocol stage.
First provider_off/accounting success fields remain historical.

Both once intents are consumed. The second reference, all174 pages, root,
context, consumer, mappings, claims and module remain pinned. Host cycle
complete=false/operation_uncertain=true despite clean completed captures.
Only this family's typed sample/gfx-snapshot is admitted. No retry, additional
power commands, application work, replacement owner, free/unmap/unload or
compensating PM put is admitted. The GPU has not reached a verified second OFF.

The [outcome JSON](2026-10-09-gfx-native-idle-cycle-live-outcome.json), SHA
`68ffd07ebf011af6369f9250396e77d8b1e65bf2d5d76b3dc3b0888b67e1a3ed`,
binds64 exact raw/source/artifact inputs and all four operations. Complete short
state rows are present immediately, maximum351 bytes including prefix/newline.
Separate startup and terminal reviews qualify their respective scopes. All
prior frozen sources, qualifications and receipts remain unchanged.
