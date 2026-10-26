# Retained native power-cycle candidate

The distinct candidate at `out/gfx-retained-power-cycle/candidate` is built and
finalized for one fresh-boot experiment. It has never been loaded. The preceding
owner completed one actual native PWRGATE and strict physical OFF; retained
objects, pages and receive journal were unchanged over 105.467723 seconds.
That establishes one shutdown, while same-owner restart and repeatability remain
unverified. See the [actual shutdown evidence](2026-10-09-gfx-native-powergate-drain-live-outcome.md).

| Final input | SHA256 |
| --- | --- |
| Owner module | `abf4ef3c709c3a775db2fa897dbbe1ba7edbb9868000848ac8283417f9fb7608` |
| Build receipt | `1762f50dcaa0a321c0003cee3ad63dba83cb50159599bc72bbf9c2444b5afe69` |
| Preparation | `aca3b33c2b35cafe31b1e8d6463f8b56181f0644dc2499a14fc5c4a4fcde7aed` |
| Selected source v6 receipt | `4f8288982b3d2e926cce11ebe800744ea92f668008e77600929d691319e3ec9a` |

The W=1 build returned zero with no warnings or errors and matches the installed
`7.1.13-m4rch-gpu-native-reset` kernel. Actual C ASan/UBSan replay passes 102 cases,
including the transformed receive worker and separate coordinator. Python replay
passes 101 checks, including six cold-main and ten resident-main flows. Independent
reviews bind the native ranges, source, qualifications and final candidate. Root
checked ten artifacts, twenty owner sources and seventeen preparation inputs.
The actual preflight CLI refuses the current boot before native sysfs or GPU
access. The prior family refuses the distinct new receipt.

The first drain/PWRGATE/OFF implementation remains unchanged. A second intent
requires the original returned first-OFF report, raw objects, all owned pages,
receive journal and exact log delta; host history and kernel once state cannot
be reset. It preserves the first epoch's flags, all 174 page pointers and physical
addresses, root, context, consumer and exclusive claims. A distinct intent also
blocks the actual receive worker without rewriting first-epoch history.

One new PM reference must produce fresh ACTIVE/accounting and physical evidence.
Fresh ASC CTRL/STATUS and mailbox RX/TX must match the original cold boundary:
START clear, STATUS `0x6a`, RX empty and TX available. Only that boundary admits
one START, autonomous HELLO12 and the exact two endpoint-map replies. The native
driver's HELLO and final-map states support a bounded management hypothesis for
one separately owned PWRGATE `0x202`, its own native ACK, checked CPU stop,
separate paired OFF, second PM put and strict physical OFF observation.

This experiment supplies no INIT220, application endpoint starts, new root or
context, firmware DATA restore, application queue reset, work or backing release.
An unknown or failed result pins resources and seals further controls. Diagnostics
explicitly distinguish historical first-OFF fields from current second-epoch state.
After either consumed OFF, unsafe powered MMIO is skipped. A successful management
roundtrip would still leave application rejoin, execution, rendered pixels and
joined DMA retirement unproved.

Current boot `16868560-efd7-4c98-b58d-45cb88280d46` retains the preceding owner,
whose PM reference is consumed and whose compiled API has no reentry command.
Only its existing typed diagnostics are admitted. A normal fresh boot is needed
for the new candidate. GRUB default5 and the installed kernel remain correct.
The exact next commands are recorded in the kit's `READY.md` and the boot guide.
