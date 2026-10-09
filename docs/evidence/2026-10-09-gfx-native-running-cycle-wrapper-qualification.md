# Native Running and HOST ON Python qualification

The distinct `gfx_native_running_cycle_scope` version10 admits `sample`,
`gfx-snapshot`, one first `gfx-powergate` and one `gfx-native-running-cycle`.
It adds two ordered management barriers to the frozen version9 retained cycle:
exact fresh EP0 BOOT word `0x0070000000000020` after HELLO12 and both exact map
ACKs, followed by one owned HOST request `0x00b0000000000020` and a fresh exact
EP0 reply with that word. Both barriers must complete before the second own202.
Neither20 frame is a shutdown ACK; that predicate remains EP0 type7 low8=1/2
after the own202, followed by checked CPU stop, paired OFF, sole second PMput,
strict physical OFF and accounting.

Selected Python qualification `out/gfx-native-running-cycle/wrapper-qualification-final-v2.json`
passes102 targeted cases, four actual cold-main and ten actual resident-main
flows, SHA256 `bc0a8396c901708854a9036573e54ed52d72d6e21490933170078e3276716d60`.
Every native read, process and command write in those main flows is intercepted
in RAM; the saved54e2 first-OFF data is copied as a fixture. Cases cover exact
new messages/order/budgets, missing or weakened declarations, complete six-row
groups and actual C replay flags, mixed/old families, previous command/startup/
preparation rejection, six consumed boots before native access, first-proof
rebuilding, both durable intents and lost host state. Frozen v9 Python74/4/10
composes through exact pins; unchanged raw-mutation/syscall cases are not rerun.

First-OFF predicates and the rotated-log join delegate to the frozen contracts.
Second admission rebuilds the completed original first typed `gfx-powergate`
report, retained objects/owned pages/journal/decoded journal and both logs, then
checks all raw hashes. It requires own ACK, checked CPU stop, paired OFF, strict
physical OFF and usage0/suspended/held0. Later cached historical flags never
qualify that proof. Separate durable intents preserve first-epoch evidence and
prevent a missing state file or uncertain delivery from admitting another
power command. Current kernel identity, accounting, transport and physical
gates remain mandatory because saved observations are non-atomic.

Fresh preON remains STATUS6a/6c; postON permits STATUS6a/6c/6d only after the
separate second paired ON, with exact6d requiring its ONcomplete and held second
reference. START must be clear, RX valid/empty and TX valid/available. Four
operands refresh before/after ON and after START intent, then a fresh CTRL RMW
performs START. The shared HELLO/map/BOOT budget remains4001 polls/4000 nominal
milliseconds and the separate HOST budget is2001 polls/2000 nominal milliseconds.
The host journal retains at most16 removed frames and reserves two slots before
B20 for its reply and the later shutdown ACK. Fresh first history, all174
identities, PM accounting and CPU/FIFO operands qualify before and after HOST
intent, after its reply and before202. Poll bounds are finite; jiffies limits
do not claim a hard wall-clock upper bound.

Selected C199 ASan/UBSan qualification `owner-qualification-final-v2.json`,
SHA `aaf2e76d651fbff245b169a500468b507a105cdbdb1d991b9469ea6c240fd50a`,
binds source receipt `d5ed3909257d659816e2c23cebe43f72308aa0677efa3660b5e76758b56ee36d`,
the actual header, separate coordinator core and copied receive worker.
Finalizer checks require actual Running→ownedB20→freshB20→202 replay and observed
BOOT20 simulation, plus complete six-row phase groups. Measured maximum421
bytes lies within the511-byte profile bound; equality is not required. These
RAM replays do not establish a new hardware reentry or second physical OFF.

The finalizer binds frozen v9 receipt027b/preparation2a8/source313135/C135/Python74.
Three dispatcher/build files change; the idle header is replaced by the running
header and the coordinator stays byte identical, preserving20 sources. It
checks source/C/Python pins, clean W1 diagnostics, vermagic and provider imports,
then exclusively creates a new receipt and `native-running-cycle-preparation.json`.
Root performs the future build, finalization and hardware execution separately.

Actual54e2 failed at BOOT20 because the old candidate wrote202 immediately after
map ACKs. The new sequence is supported by the cold bootstrap order and native
Running8/HOST ON20 handling. Native `_iopValidate` defaults to8; parent host
flags can select6. Actual native runtime flags, callback skips and remote state
remain unobserved, so this is an observed protocol hypothesis. All174 identities,
context, roots, maps, consumer and module remain retained. No INIT220,
application endpoints/root/context/work publication, DATA restore, application
queue reset, unmap or free is admitted. Hardware second OFF, application reuse,
repeatable execution, rendering and DMA retirement remain unverified.

Portable selection JSON SHA256 `3cb229f312ec7385c6f69e9443cdb55125e35222133e3641102635bbb413f690` binds 79 exact local inputs, including frozen v9 evidence, the native boundary and actual54e2 protocol comparison.
