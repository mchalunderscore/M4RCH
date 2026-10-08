# startup reaches slot22; matching private AGX audit expanded

boot c22c7dac-2c96-41b7-8796-cf1a92a5cb7b, trial source3f79d32.
regular GPUC001 kernel7.1.13-m4rch-gpu-contract, promoted package7.1.13-2,
GRUB default1 and USBR001 backupentry3 unchanged. all three USB role providers
and PD controllers bound before/after. user confirms desktop, input, USB and
networking remain normal. no macOS or bootloader change required.

gate1 shadowwalk passes; gate2 returns0. firmware advances from primary aac8
to slot22 startup PC24210. new2560-byte footer-valid EHLC/Crg8 crashlog and
one EP1 fatal notification. FARfffffc2001204004, ESR9600004f; a32-bit write
uses native X10fffffc2001200000 plus4004. physical289004004 belongs to the
existing read-only page289004000. this is a new bank, beyond the prior
primary-register permission barrier; it is not proof of full startup.

29 live owned-RAM snapshots, no observer errors, one unique framehash.
control read/prefetch/write remain0/0/1: the pending opcode16 was NOT consumed.
main now changes at32c and344..347, alongside earlier header/power/status
writes. no queue, rendering or initialization-complete claim.

next candidate: bounded native continuation24210..2427c covers two writes
at slot22+4004/+4010. an earlier selector replay24048..2427c covers118
instructions and eight register writes across primary288004000 (alreadyRW)
and slot22 page289004000 (newRW). captured native DATA/objects/registers,
explicit zero device-register RAM; earlier replay assumes preserved registers
and native state-query result3. stops BEFORE timer helper; later callback,
device semantics and complete function are unqualified. unknown code/memory
aborts. no proprietary instruction listing in tracked evidence.

same100 device leaves/47 owned pages/147total;36 device pages writable.
slot22's first page289000000 stays read-only. opaque descriptor flag remains
unchanged: CPU HAL flags are not assumed equivalent to firmware flags.
graph bytes are identical; no new addresses, controls, doorbell or work jobs.
14 mapping/serialization/allowlist tests pass, both bounded replays pass,
W=1 eight-helper build passes without warnings, receipts/modules match.
actual trial artifacts: primary-late-candidate; next: slot22-startup-candidate.

private Apple audit: /boot/GPUC003/private-apple/com.apple.AGXG16X353.14,
matching25G83 SHA3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e.
private checksum,13-row PIO parser and platform checker all pass again.
configureDevice constructor supports resource22 base at primary+1000000;
the existing8000-byte extent remains a donor hypothesis. native pointer and
fault independently corroborate the chosen VA. no IRQ/reset proof.

broader static checks corroborate shared sizesc18/1048/e10 and status mapping
notification pointers48e0/48e8. notification backing remains absent from our
fixture: qualify extent/ownership before adding it. host isFirmwareInitialised
checks CPU-only bookkeeping; don't treat it as firmware readiness evidence.
six matching private audit targets recorded for allocation/coherency, complete
shared objects/receive channels, resource inventory, power defaults, boot
completion/retirement and MMU prerequisites. these are next audits, not claims
that their behavior has been fully decoded or should be blindly replayed.

evidence: docs/evidence/2026-10-08-slot22-{startup-result,startup-crash,model,
candidate,private-mapping}.json and2026-10-08-private-agx-audit.json.
raw capture: asc-graph-init/boot-c22c7dac-2c96-41b7-8796-cf1a92a5cb7b.
implementation-derived work, NOT clean-room. binaries/full disassembly/TEXT
remain private and excluded from Git and return archives. README provenance
corrected to distinguish early metadata work from current binary-exposed work.

NORMAL LINUX REBOOT required before another root publication: current backing
pinned/stopped, AP_QUIESCED/IOP_SLEEP acknowledgements absent. never force
unload or republish on this boot. after r verify fresh boot/USB/build receipt/
firmware contract, then:

    sudo -n python experiments/t6040-gpu/run-root-envelope.py out/gpu-gravity-contract --graph --run

retain30-second mailbox/live-owned-RAM capture; decode any new crash, check
control consumption and shared-state changes, confirm peripherals. use the
matching private AGX evidence to qualify broader next segments and missing
objects. rebuild needs build-root-envelope.py out/gpu-gravity-contract
--control-refresh. no automatic reboot performed.
