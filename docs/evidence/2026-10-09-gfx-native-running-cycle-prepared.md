# Native Running cycle candidate prepared

The distinct version 10 candidate is built, finalized, reviewed and ready for one
fresh-boot experiment. It has never been loaded. The current version 9 owner on
boot `54e21e8f-b6f8-42cc-a5e5-e3f42831b870` remains sealed with its second power
reference held and all 174 pages retained.

That boot proved a limited firmware transport restart: the first shutdown reached
strict physical OFF, a separate power reference and paired ON restored ACTIVE,
one START write read back correctly, and autonomous HELLO12 plus both endpoint
map ACKs completed. The following type7 `0x20` frame was correctly excluded from
shutdown proof. No second CPU stop, paired OFF or power-reference release followed.
Current CPU progress and pending mailbox contents remain unknown.

The matched native RTBuddy handler recognizes this type7 `0x20` as Running.
Native ON notification separately sends HOST typeB `0x20` and waits for its reply;
the existing cold source and capture show the same separate handshake before
application/root setup. Native runtime flags and callback parity remain unobserved.
These findings justify the following bounded experimental order:

1. Preserve the qualified first strict OFF and all retained identities.
2. Acquire one new power reference, complete a separate paired ON, and execute one
   freshly guarded START followed by HELLO and exact endpoint-map ACKs.
3. Observe exact autonomous EP0 `0x0070000000000020` within the shared boot budget.
4. After fresh admission checks, send one owned HOST `0x00b0000000000020` and
   require a fresh exact EP0 reply, reserving journal capacity for reply and ACK.
5. Refresh admission checks and send one own `202`. Only type7 low1/2 can qualify
   as the shutdown ACK; checked CPU stop, paired OFF, one second PM put and strict
   physical OFF remain mandatory.

Unknown results seal further controls and retain resources. The path admits no
INIT220, application/root publication, context reattachment, DATA restoration,
queue reset, GPU work or memory release.

The W1 module build completed with no warnings. Actual-header C qualification
passed 199 ASan/UBSan cases; Python qualification passed 102 cases including four
cold and ten resident main flows. Six complete phase rows measured at most 421
bytes including prefix and newline, below the 511-byte bound. Independent source
review verified 127 inputs; compiled review verified 210. The root preparation
record binds 39 inputs and preserves the frozen baseline qualifications without
rerunning them. The actual new preflight CLI refused the current boot before
candidate/native/sysfs/GPU access and created no preflight output.

Candidate: `out/gfx-native-running-cycle/candidate`. Selected source:
`out/gfx-native-running-cycle/prepared-owner-v2`.

| Artifact | SHA-256 |
| --- | --- |
| Owner module | `c0dd4c7f939e328b83ede890216df099b1935a9af3b8e0bd3a7593213995a037` |
| Build receipt | `32b2ff0c647eae38a4f74486dc4f85793fdbfe478d60ab96555eb290d4564c65` |
| Preparation | `a2237389fa172c4f319c482df7ab9b58bbd551339ce690c8789ab2ae90a83303` |
| Source receipt | `d5ed3909257d659816e2c23cebe43f72308aa0677efa3660b5e76758b56ee36d` |
| Final compiled review | `127afbf9e2cb9204c5fd72fb683e472195b993012f7a1d6668966afd2c24261a` |
| Root prepared record | `2de39ddb4bd9224272fdde73514c0b1eac9d90f6f614eb6795037a3990a1fa10` |

The next trial requires a fresh normal user boot. Six consumed boot IDs are
refused. GRUB default 5 already selects `7.1.13-m4rch-gpu-native-reset`; kernel
and boot configuration were unchanged. No current owner was unloaded or replaced.
Second shutdown, a full management roundtrip, application rejoin, joined DMA
retirement and rendered pixels remain unproved. The accelerated desktop goal is
unfinished.
