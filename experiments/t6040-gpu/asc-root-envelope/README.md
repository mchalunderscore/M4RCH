# Minimal G16S root reader trial

This is an explicit negative control, not a complete initialization graph or
rendering trial. The hash-qualified RTKit3255.160.4 parser compares the first
root u64 with `0c8aa322039604c0`, copies c8 bytes, then requires root+2c to be
nonzero before reading main/Region C. We supply the correct identifier and
zero at +2c. The expected diagnostic is:

> Host-mapped FW allocations are disabled

A newly written copy of that rejection in firmware DATA would corroborate
root translation, visibility, mailbox delivery and the interface comparison.
Transmission alone, silent timeout, or an unrelated firmware fault proves none
of those. Raw before/after DATA snapshots are retained for crashlog decoding.
The current runner's string detection is a useful observation, not a substitute
for decoding a structured crashlog and proving the report belongs to this run.

Gate 0 refuses. Gate 1 allocates three owned 16 KiB pages, constructs an isolated
L1/L2/root shadow mapping, cleans caches, validates physical addresses against
42-bit OAS, and frees all pages. It does not touch firmware tables or GPU MMIO.
Gate 2 requires cold stopped status6a and an empty receive FIFO. It validates
bootstrap TEXT/DATA path after the IOP/AP ON handshake, permits only the
observed AF bit10 on table descriptors, preserves firmware-populated slot2 (`200105fff744cb`) pointing to the
separate reserved page105fff74000. That page must be entirely zero; the probe
installs only its empty child slot pointing to the owned leaf table. If slot2
is absent, it may instead install the owned L1 there. Unexpected descriptors
or occupied child pages refuse. Existing firmware descriptors are preserved. It sends the envelope to endpoint32
after the established crashlog/HELLO/maps/IOP ON/AP ON/START32+33 sequence.
No main, hardware data, queues, shaders or SGX register writes are supplied.

The root leaf attributes match the donor's `PROT_FW_SHARED_RO` bits: global,
FW AP1, uncached, access flag, high GPU-access bit. These are a candidate
permission contract, not native acceptance proof. Existing slot0 is preserved.

Once a root is transmitted, pages/table mapping/power reference are retained
and the module pins itself, even if core stop succeeds. No force-unload or
warm restart. A host hang remains possible; save work before the cold trial.
Before-start failures remove the mapping and free pages. Started failures pin.
The firmware rejection is intentional and may halt GPU firmware; a following
reboot is required to reclaim retained resources and obtain a fresh controller.

Build against the currently booted isolated trial:

```sh
python experiments/t6040-gpu/build-root-envelope.py out/gpu-gravity-contract
sudo python experiments/t6040-gpu/run-root-envelope.py out/gpu-gravity-contract
```

The second command performs read-only validation and unloads its samplers.
After a normal reboot, repeat it with `--run` only when ready for the rejection
trial. The runner validates current kernel notes, module hashes, fresh ADT,
TEXT/DATA table translations and the exact firmware image outside two tagged
8-byte boot metadata payloads. No instruction bytes are ignored. Attempt intent,
dmesg and DATA snapshots are persisted; at most one attempt per boot is allowed.
It does not change the boot entry, install a kernel, or reboot automatically.

The stage2 metadata is mBoot18000.161.10; the two variable TEXT payloads have
raw tag bytes GKTS and ECAP with length8, at59841 and59924. Their meanings have
not been established here. Both historical/current captures match everywhere
else. The image checker rejects changed tags, lengths and instruction bytes.

Full initialization still needs the complete G16S object contents, channels,
ownership, topology, register mappings and voltage conversion. In particular,
current ADT perf-state-count16/gpu-num-perf-states15 differs from the donor's
11-row assumptions. Do not truncate or transplant those ladders to run this test.
