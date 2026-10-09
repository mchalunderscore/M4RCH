# Live KSM queue installation and next scheduler-start batch

On boot `98ab7030-1dc4-4113-a435-360c0c7209e2`, kernel `7.1.13-m4rch-gpu-contract`, the prepared first-queue-install candidate completed its bounded hardware trial. Fresh kernel/ADT/TEXT/parser checks passed. Module SHA256 `d954dce9f5f20260f8eb5f10d289a43ad43bc4ad7c05c987caaabaf8a3886c49`.

Both firmware scheduler rows changed from zero to installed flag1. TA queue0 has FW ringfffffc2000b1c000/GPU10000cc000/data-master0; fragment queue1 has FWringfffffc2000b24000/GPU10000d4000/data-master1. Both geometry fields10, header0, exactly as the matched consumer predicts. This confirms first-use config1a now installs the supplied queue metadata. It does not prove hardware fetch or shader execution.

Root0/1 notifications and both config/add-kicks pointer batches were consumed; queue pointer completed/prefetch/producer2, add-kicks count0->4. Only six queue-state bytes changed in the owned render data. Target and completion/SPM page remained identical; no crash header, application mailbox response or receive13/14 change during30seconds. AP-quiesce/IOP-sleep ACKs, ASC stop readback pass. Probe/context/GFX backing remains retained until reboot. User reports desktop, built-in input, USB and networking normal.

## Next combined candidate

`out/owned-scheduler-start/{prepared,live-candidate}` batches first-timeline setup and shared owner-context association while preserving the installed queues, native timestamp1 TA/3D records, register lists, command pool, shaders, target and resource aliases. It changes28 backing bytes:

- Initial NOPtimestamp0 predecessor changes from self0 to modulo40 wrapped predecessor `0xffffffffff`, preserving its seven-bit queue identity. Actual timestamp1 TA waits on TA0; fragment waits on TA1 and its own queue1 timestamp0.
- Config26=1 publishes the same wrapped baseline through config2a. Firmware branch1922c..19238 and table13c3a0 are qualified against exact captured TEXT.
- TA/fragment queue-state9c and config4a share the TA-owned context `fffffc2000b18200`, consistent with a common owner and Gravity's shared per-public-queue context. Config52=1 activates association. Matched consumer19b80..19b8c is checked. Base-M4 context seed is retained; raw service fields56/5a/5e remain zero hypotheses. These are not asserted ASID1 or proven M4 Pro defaults.

The zero-predecessor NOP was a potential self-dependency, not proved to be the observed stall: initial hardware counters are still unqualified. Shared context installation may reveal additional policy, geometry or translation requirements. Context assignment is distinct from the already-live UAT context1. No direct additional host SGX MMIO writes are introduced; firmware processes the requested configuration.

Builder verifies all actual timestamp1 work bytes remain unchanged. Matching W=1 module build, hashes, Python compilation and diff checks pass. Analyzer now captures baseline table entries, per-KSM-queue owner-context pointers and38-byte owned context contents, as well as installed rows/cursors/crash/target/completion evidence.

After normal reboot into Linux, use `run-root-envelope.py out/owned-scheduler-start/live-candidate --graph`, then the same with `--run`; analyze the new boot capture with `analyze-owned-work.py`. Do not repeat INIT alone, retry warm INIT, or force unload. No kernel/default-entry changes required. Exact prior capture: `out/owned-queue-bind/live-candidate/asc-graph-init/boot-98ab7030-1dc4-4113-a435-360c0c7209e2`. No rendered pixels or accelerated desktop verified. Private implementation-derived research; not clean-room material.
