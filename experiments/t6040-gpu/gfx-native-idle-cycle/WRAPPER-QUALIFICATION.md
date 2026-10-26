# Native idle-cycle Python qualification

The distinct `gfx_native_idle_cycle_scope` version9 admits `sample`,
`gfx-snapshot`, one first `gfx-powergate` and one `gfx-native-idle-cycle`.
Its stage-specific contract permits only fresh STATUS6a/6c before the separate
second paired ON. After that ON, fresh STATUS6a/6c/6d may qualify; exact6d also
requires the own second coordinator ONcomplete and held second PM reference.
START must be clear, RX valid/empty and TX valid/available. All four operands
refresh after ON and after START-intent logging, followed by a fresh CTRL RMW.
STATUS alone is never success, application-rejoin or physical-OFF proof.

Selected qualification `out/gfx-native-idle-cycle/wrapper-qualification-final-v2.json`
passes74 targeted cases, four actual cold-main and ten actual resident-main
flows, SHA256 `565b4bb2d72eb56f498f8450e3c8f57e27b3aa08460fee4404c9bcb390753a08`.
System reads, subprocesses and command writes are intercepted in RAM. Actual
boot9626 first-OFF data is copied as a fixture. Cases exercise exact stage sets,
weakened preON6d and postON sets, missing secondON/ref requirements, new and mixed
families, previous command/startup/preparation rejection, all five consumed boots
before native access, first-proof rebuilding, both durable intents and lost
host state. Frozen v8 Python69/4/10 composes through exact input pins without
repeating its unchanged raw-mutation and syscall-fault cases. The preliminary
72-case qualification is preserved as historical.

First-OFF predicates and the exact rotated-log join delegate to frozen v8 and
its preceding immutable contracts. Reentry requires the completed original
first successful typed `gfx-powergate` report, clean raw retained captures and
journal, own management ACK, checked CPU stop, paired OFF, strict physical
word and usage0/suspended/held0 accounting. Raw report/objects/owned/journal/
decoded-journal/both logs are hashed again before second admission. Later cached
first flags cannot qualify it. Separate durable epoch intents preserve that
original proof and prevent a missing state file or uncertain second delivery
from permitting another command. Current kernel identity/physical/transport/
accounting gates remain mandatory; saved observations are non-atomic.

The selected C135 ASan/UBSan replay binds source receipt `313135be…` and the
actual new header, coordinator and copied receive worker. The finalizer requires
actual stage-guard exercises and replay of observed6c→pairedON→6d, along with
bounded complete newline rows. Measured maximum418 bytes must lie within the
511-byte profile bound; equality is not required. C135 qualification is a RAM
replay and does not establish actual START, HELLO, ACK or second OFF.

The finalizer binds frozen v8 receipt969/preparation162/source59ca/C115/Python69.
Three dispatcher/build files change; the native retained header is replaced by
the native idle header while the coordinator remains byte identical, keeping20
owner sources. It checks the selected C/source/Python pins, clean W1 diagnostics,
vermagic and provider imports, then exclusively creates new receipt/preparation
files. Root performs the build, finalization and hardware execution separately.

All174 page identities, context, host roots, maps, consumer and module remain
retained. No INIT220, application endpoint/root/context/work publication, DATA
restore, application queue reset, unmap or free is admitted. Unsupported6e/48,
preON6d, stale/invalid transport and unknown outcomes seal further power controls.
The only new hypothesis is postON idle6d admission under the separately qualified
second ON/reference. Actual full roundtrip, second physical OFF, application
reuse, repeatable execution, rendering and DMA retirement remain unverified.
