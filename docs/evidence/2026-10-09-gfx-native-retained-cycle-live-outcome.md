# Native-ordered retained cycle: ON qualified, post-ON status guard refused

Boot `96264748-b049-403f-9240-975716f71d0c` repeated a verified first native
shutdown. The retained cycle restored physical ACTIVE with one new PM reference
and completed its separate second paired ON. Fresh STATUS48 then changed from
`0x6c` before ON to `0x6d` after ON. The prepared known6a/6c guard refused before
START. Firmware restart and a second shutdown were not attempted.

The selected owner SHA is `4f9d6ea85df700166583e6992e57d935a8b68ea19b695cde07e1a93bb783d062`,
receipt `969692c5ee0880197cda6349bf8b04e1c580ecb32aa374e6533f713d0447c3d4`,
and preparation `162c04373f72999f5f62a5948e7ed2ec57504a585c98ce9ef31a27a86fb60ea9`.
The saved loaded GNU note matches the qualified owner through the pure ELF
parser; refcount1. Kernel `7.1.13-m4rch-gpu-native-reset` and all preflight
kernel/artifact/source/USB/PD/role/resource guards passed.

The cold no-work trial returned zero and qualified the exact version8 session
marker and four typed commands. Initial recovery completed0/2; all174 joined
pages remained retained. The first shutdown drained eight qualified EP32 frames
and recorded the service epoch, own202 and selected native EP0 ACK after four
polls. Fresh empty RX, native idle, two fresh CPU CTRL clears and readbacks0/0
preceded paired OFF and one PM put. The first physical sample was strict
`0x0f000300`, BUSY0/domainOFF, held0/usage0/suspended/error0. Root rebuilt and
saved the exact seven-input first-OFF admission proof.

| Second stage | Saved result |
| --- | --- |
| Before second PM get | Strict OFF `0x0f000300` |
| One second PM get | Return0, held1/usage1/ACTIVE/error0, physical `0x1f0003ff` |
| Fresh pre-ON boundary | CTRL0, STATUS6c, RX20001, TX20001 |
| Separate epoch2 paired ON | Return0, full REQ2000 and three vote4 readbacks; native STATUS0 bypass, no ACK claimed |
| Fresh post-ON boundary | CTRL0, STATUS6d, RX20001, TX20001 |
| Retained return | `-16`, cold-boundary-unqualified, STARTintent0/protocol0 |
| Later typed diagnostic | Fresh physical ACTIVE and clean held1 accounting; ASC/MMIO skipped |

No second START write/readback, HELLO/map reply, second202, ACK, CPU stop, paired
OFF or PM put occurred. The second reference stays owned. Both once intents are
consumed. Complete five-row phase records appeared in the immediate captures;
the largest actual new state payload was342 bytes excluding the `m4rch ` prefix
and newline, or349 bytes including both. This fixes the preceding
trial's record visibility problem without changing the hardware outcome.

The later physical sample was64.681403 seconds after the first-OFF physical
sample. All69 object pages, all174 owned pages and the full receive journal were
byte-identical across first OFF, the returned cycle and later diagnostic.
Power+652c6648, journal51176 and doorbells8 remained unchanged. These non-atomic
samples support cessation in captured buffers, not global writer identity or
joined DMA retirement. Later STATUS6d/CTRL/FIFO fields are cached from the
245.303004 post-ON boundary; the282.524330 PMGR word and accounting are fresh.
First provider_off_observed/accounting_ok fields are historical successes.

The owner stays pinned and sealed; only its typed `sample`/`gfx-snapshot` are
admitted. No retry, replacement owner, additional PM get/put, wake/reset/control,
new root/context/work, detach/free/unload is admitted. Same-owner roundtrip,
application rejoin, safe retirement, GPU execution, rendered pixels and the full
accelerated desktop remain unverified.

The [machine-readable outcome](2026-10-09-gfx-native-retained-cycle-live-outcome.json)
binds64 exact inputs, including all closed operation captures, first-OFF proof,
loaded identity, selected owner/source and preflight. JSON SHA
`d95c2ecbb5f347db9bbdec28ec43e6d7e0008470f3b472595a80206c0794bdb3`.
Separate startup and terminal reviews qualify their own scopes. Prior frozen
preparation, receipts and captures remain unchanged.
