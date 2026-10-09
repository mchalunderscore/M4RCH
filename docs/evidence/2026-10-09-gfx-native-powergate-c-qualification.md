# Native PWRGATE source and C qualification

The next candidate adds the missing native management PWRGATE request before
CPU stop and paired provider OFF. On boot `94cb4163`, the native STATUS0
coordinator completed both PMP/PMC transitions and the normal PM put returned 0,
but the physical word remained `0x0f000b00` with BUSY11 set. The retained
firmware-owned power counter then changed 25589→57056 over about 262 seconds.
That result does not establish teardown, recovery or safe resource release.
The current owner retains all 174 pages and admits only `sample` and
`gfx-snapshot`; the new candidate has never been loaded.

The source is `out/gfx-native-powergate/prepared-owner-v5`. The companion
JSON binds its exact source receipt, the actual C qualification, the matched
native ranges and the built candidate. No GPU, mailbox, MMIO, PMGR, PM-reference,
mapping, module-load, reboot or APFS action was performed by this qualification.
Private binaries and full disassembly remain under ignored `out/private-apple`.

The matched 25G83 kernelcache's request table selects
`0x0060000000000202` for native ordinal 2 PWRGATE. Normal descending transition
waits for native IOP status 2 before disabling mailbox event sources and invoking
ordinary `stopCPU(false,false)` in the nonhibernate path. The new bounded
management dispatch and ACK-handler review explains the wire-to-host conversion:
type bits 52..55 equal 7, and ACK low8 equal 1 or 2, while native host status 7 denotes
the pending transition, convert to native status 2. The new owner emits only 202;
accepting either native ACK value does not introduce a SLEEP201 request.

| Matched native range | Bound finding |
| --- | --- |
| `0xfffffe000b1f1e58..1ec8` | Type-nibble7 dispatch preserves the full payload for the power ACK handler. |
| `0xfffffe000b1f2f7c..3014` | ACK low8 in{1,2} selects native IOP status 2 from pending status 7. |
| `0xfffffe000b1e00c8..08ac` | Native202 transition waits for status 2, disables mailbox event sources, then ordinary CPU stop. |
| `0xfffffe0008a3fc54..fcf4` | V6 idle requires either STATUS48 low bit; the saved GFX ADT omits optional CTRL40 gating. |
| `0xfffffe0008a3fcf4..fda4` | CPU stop reads CTRL44 freshly, clears 0x10, reads freshly again and clears 0x20. |

The native interrupt method dispatch is positively bound to
`AppleA7IOP::enableMailboxInterrupts(false)`, which disables host event-source
objects. It does not qualify another raw ASC mask write. This owner uses a
polled receive worker, so the terminal intent seals and cancels that worker while
holding its shared mutex. A queued worker must acquire the same mutex and observe
the seal before touching the transport. No synchronous cancellation waits under
that mutex.

The distinct dispatcher admits only `sample`, `gfx-snapshot` and one combined
`gfx-powergate`. Before the sole management request it requires retained
backing, one active PM reference, START set, no work, clean receive state, an
empty RX FIFO and available TX. It admits the known initial diagnostic phase 2
after 0/1 completed cycles, or healthy phase 0 after 2 cycles, with consumed control
cursors and their corresponding request/counter state. Initial recovery and all
graph, render, context and allocation identities remain unchanged.

Only the fresh ACK permits the pre-stop idle check. The owner then performs the
two fresh native CPU-control RMW operations with readbacks. It refuses a second
write if START reappears, and requires RX empty after the ACK and immediately
before CPU writes. Only a checked stop delegates to the unchanged paired
PMP/PMC OFF and sole PM put. Unknown ACK, timeout, pending or invalid RX,
nonidle status, failed CPU readback or reasserted START seals the intent and
retains PM/backing without an OFF attempt. No separate STOP/OFF bypass or work
command exists in this profile.

Post-ON startup failures also retain their existing resources. The old
`retire_firmware` and `stop_firmware` fallback paths no longer send AP/SLEEP
requests, write CPU control, turn power off or clean up. Their unique startup
unknown marker admits no commands, including diagnostics, in both the owner and
the wrapper contract. Existing pre-ON allocation-only cleanup remains separate.

The actual new header and the transformed startup fallback branches passed 55
C cases under AddressSanitizer and UndefinedBehaviorSanitizer. Cases cover both
native ACK values, initial healthy/diagnostic state, durable single intent,
forbidden commands, wrong or late ACK, RX/journal limits, the native idle retry
boundary, both CPU-write failures, fresh second-read preservation, START
reassertion, negative PM put, physical OFF failure, retained startup failure and
the explicit unknown-startup command barrier. Existing provider/receive helpers
are mocked at this new-header boundary; their frozen core/adapter/OFF
qualifications remain separate. LeakSanitizer is disabled because the host
ptrace restriction prevents it from running; this replay allocates no heap
backing.

Root built the selected `out/gfx-native-powergate/candidate` owner against
`7.1.13-m4rch-gpu-native-reset` with W=1, result 0 and no warnings/errors. Module
SHA-256 is `7bced3badf35f4e99ade95428622e26e3259fbc37c16de13eb0d845e9b6745bc`.
At this checkpoint, final Python-wrapper qualification and the candidate receipt
are pending. The source qualification does not authorize loading this candidate
over the sealed current owner.

This tests a distinct native management/CPU-stop boundary. It does not reproduce
the unresolved native mapper-inactive dispatch or establish the effect of native
firmware-unmap on the joined context. All 174 pages, UAT mappings, context,
consumer and module remain retained on every result. Even an ACK plus physical
OFF and stable sampled words would leave cache/fabric drain, fresh firmware
DATA, restart, complete DMA retirement and triangle execution unproven.
