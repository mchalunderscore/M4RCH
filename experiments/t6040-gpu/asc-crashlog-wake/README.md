# Bounded crashlog-only RTKit boot and shutdown trial

Build against the exact running GPU-contract kernel with a generated
boot-contract.h containing FW_DATA_BASE and FW_DATA_BYTES from fresh ADT.
Validate boot ID/build ID/module hash and every conflicting module before load.
The probe starts endpoint1 only and echoes one firmware offer only if wholly
within reserved DATA, aligned, and disjoint from Linux System RAM. No new DMA
allocation, RAM write, application endpoints or initialization objects.

Requires IOP ON, AP ON, AP QUIESCED and IOP SLEEP acknowledgements, stopped
controller and empty RX FIFO before normal unload. All incomplete retirements
pin resources until reboot. Never force removal. This is not full GPU teardown.

The original probe succeeded on cold startup once; repeating ASC START alone
from status6e produced no messages. The wake variant admits fresh6a, or6e only
with wake_gate=1, sending management IOP INIT220 as in apple_rtkit_wake. That
variant is built but has no native qualification yet. Repeat proof remains open.
