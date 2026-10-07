# Experimental structural GPU initialization

Current GPUC002 helper publishes21 structural object pages and32 device pages.
Slots33 Bumper and35 DFenderMGPUCfg use matching25G83 static mappings, qualified
by five exact native reads. Only their two16KiB device pages are writable;
other device leaves remain read-only. Hardware mask input is0xf6fdb at+0x2560,
third word0 at+0x2568. Slot32 ScratchRam extent is0x20000 from the matching map.
Opaque zero objects remain fixtures, not a complete production configuration.
No rendering work is submitted.

`build-root-envelope.py` validates the maintained kernel/config/source and
records generated artifacts. `run-root-envelope.py --graph --run` checks fresh
ADT/kernel/firmware identity, validates shadow allocation/walk, unloads the
shadow-only instance, then publishes once after cold RTKit startup. Object
and firmware DATA snapshots are captured after stopping ASC. No auto reboot.
Published backing/mappings and power stay pinned until normal reboot; never
force-unload them. A returned helper is not proof of full initialization.

GPUC002 programmed the real Bumper mask (readback0xf6fdb/0/0) and passed the
former slot35 null write. It stopped on a slot41 counter write-permission fault
at+0x60, physical0x288e1f860. Current dense per-bank GPU virtual packing also
needs replacement with SGX-relative virtual offsets: firmware later subtracts
0xd10000 from slot29's virtual address. Review overlap permissions, complete
TLBI coverage and qualified address ranges before the next cold trial.

Earlier diagnostic RAM surrogate demonstrated only mask-consumer behavior;
it has been removed from this real-bank variant. Earlier speculative bank
scanner caused a system hang and remains quarantined. Do not rerun it.
See docs/evidence/2026-10-07-gpuc002-real-register-result.json and its linked
input source provenance/native captures. No GPU acceleration established.
