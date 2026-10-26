# Independent retained transport and management cycle review

Selected source v6 has no source blocker for one bounded, experimental retained
transport and management roundtrip. This is an offline source/native review,
not evidence that the second cycle works. Application rejoin, repeatable GPU
recovery, DMA retirement and pixels remain unproved. The current boot16868560
has the frozen de75 owner, which has no retained-cycle API; this review admits
no replacement or control on that boot.

The [portable JSON](2026-10-09-gfx-native-retained-cycle-independent-review.json)
pins the selected v6 source receipt `4f828898…`, final C qualification
`0bcc3860…`, 67 input files and 15 bounded native byte ranges. The selected
source contains 26 input and 28 output pins. Only Makefile, the owner C file
and recovery-cycle header change from the frozen successful drain source; two
separate headers are added. The first drain header remains byte identical.
No hardware action, live register read or qualification reexecution occurred
in this review. Final Python/finalizer qualification and built-module receipt
are separate joins owned by the wrapper/root reviewers.

The [actual first shutdown review](2026-10-09-gfx-native-powergate-drain-live-terminal-review.md)
already proves one own management ACK, checked CPU stop, paired OFF, PM put and
strict physical OFF with BUSY clear. Its later capture has the same objects,
owned pages and receive journal after about105 seconds. This satisfies the
missing first-OFF prerequisite of the earlier retained reentry boundary. Those
sampled buffers do not prove whole-GPU DMA retirement or retained application
state through another power cycle.

The matched native driver selects `startCPUWithOptions(0)` for stopped host IOP
status1 or2 when the running property is absent. Native endpoint memory
preservation returns true for ordinals0,1,2 (SLEEP, ON, PWRGATE). The preloaded
firmware route maps existing backing and its fixup skips copying DATA to the
target; `runCPU(true)` freshly reads CTRL44 and ORs0x10. These are framework and
provider semantics, not a guarantee of a restored reset vector, GPU UAT state
or application context. Saved SRAM backup flags do not supply a restore path.

The narrow management route gives a useful second-shutdown lead. HELLO is
handled in host IOP status4, selects protocol12 and records status5 before the
reply. Endpoint rollcall requires status5; a successful final map ACK precedes
status6. Normal started validation expects6. These are host software statuses,
distinct from ASC hardware STATUS48. Native `requestPowerState` directly sends
the ordinal-table request and has no app-root prerequisite in its bounded
body. PWRGATE enters host status7 before0x202; an own type7 ACK with low8 equal
to1 or2 normalizes to status2. That supports a limited management-only second
0x202 hypothesis after a fresh, successfully ACKed HELLO/map exchange. Native
full ON has additional endpoint/AP callbacks and metadata handling that this
probe does not implement, so the same evidence cannot authorize application
work or INIT220.

The selected code enforces the following boundaries:

- The second intent independently seals the copied receive worker. It never
  rewrites the first seal or session-failed fields to manufacture its premise.
  Invalid first evidence refuses unchanged before another PM get. All174
  pointers/PAs, maps, consumer and root descriptor identities are compared.
- A fresh strict OFF/accounting check precedes one new PM reference. Fresh
  ACTIVE and held1/usage1/error0 precede MMIO. Valid CTRL44/STATUS48/RX114/TX110
  require START clear, exact0x6a, RX empty and TX available before and after a
  separate paired ON. The sole START RMW refreshes CTRL44 immediately before
  its write. Status6e/6c/48 refuses before START.
- A separate bounded journal preserves removed words before decoding. HELLO
  must offer12/12. Maps must match saved cold base0/bitmap3/nonfinal then
  base1/bitmap3/final; the complete six-bit base is checked before replying.
  Successful final ACK precedes admission. Capacity for the own ACK, fresh
  four operands and PM accounting are required before the sole second0x202.
- Only an own EP0/type7/low8{1,2} ACK plus fresh empty RX permits native idle
  and checked fresh clear0x10/clear0x20, then separate paired OFF and one second
  PM put. After the put, observation uses only PMGR/software and retained DRAM.
  Complete is recorded only after strict OFF/accounting and final immutable
  first-evidence/identity checks. Every outcome retains all resources.

The author’s final qualification covers102 cases with ASan/UBSan using the
actual new headers, actual coordinator core and extracted copied receive
worker. This reviewer verified every qualification input pin and reviewed the
failure injections, including invalid historical first state, changed maps,
fresh START, journal capacity, invalid second-OFF status and queued worker
calls after second intent. Hardware/provider/mailbox behavior remains mocked;
the frozen first-drain qualifications compose separately. These tests do not
establish that ACTIVE/paired ON will produce0x6a, that retained firmware will
emit HELLO/maps, or that a second ACK and strict OFF will occur.

The Python first-OFF proof was also read directly. Its typed result, native
ACK/CPU/OFF/accounting predicates and rebuilt raw capture/journal/log pins agree
with the independent actual boot1686 review. Its saved observations remain
non-atomic, and current kernel identity, physical and transport gates remain
mandatory. No root publication, application endpoint/AP-on, INIT220, DATA
restore, reset vector, context reattach, queue/counter reset, unmap or free is
added by the retained-cycle candidate.
