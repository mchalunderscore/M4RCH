# First combined owned TA/3D publication — 2026-10-09

Boot `7f61235c-5ff7-41ad-8e57-cb2b5cdfcce0`, kernel `7.1.13-m4rch-gpu-contract`, candidate source `d9dba0b`, module `238fa33ab43a08c99cf2f5c9722e25c391266a51f649c76445847cec27a146d0`. Fresh metadata/table/TEXT qualification passed before the combined trial. Live context1 installed; owned TA/3D queues published with EP33 wake. This is the first transmitted combined candidate, not a successfully rendered job.

Both root work notifications were consumed (channels0/1 cursors1/1/1); control12 consumed32 refreshes. Both queue pointer records reached completed2/prefetch2/producer2 and state1c=2. Only three bytes per queue-state page changed. Target and completion/SPM page remained byte-identical. No EHLC crash header, app mailbox message or receive13/14 buffer change during the bounded observation. AP-quiesce/IOP-sleep acknowledgements and ASC stop readback returned; context/backing/GFX remain pinned until reboot. User reports desktop/input/USB/networking normal.

## Concrete configuration omission

Matched TEXT opcode15 dispatch at191f8 reads config1a at1926c and branches directly to19b80 when zero. The skipped path installs a40-byte KSM row at13dbd8+queueID*40, including FW/GPU ring pointers, header, geometry and data-master. Our prepared config1a was zero in both queues. Captured rows0/1 stayed entirely zero. Opcode14 handler1941c writes the kick count to the scheduler register path and increments firmware13c390; captured counter rose0->4. Thus firmware consumed requests for four kicks without our supplying the queue-install request. Pointer completion means control-record processing, not TA/3D hardware completion.

The supplied spec describes record layout but does not supply this first-use flag behavior. This omission is enough to invalidate the previous expectation of GPU work execution. It does not prove there are no further missing requirements.

## Prepared next combined trial

`out/owned-queue-bind/live-candidate` contains a matching W=1-clean module. `prepare-owned-queue-bind.py` checks exact TEXT identity, opcode15 dispatch and branch/store words before changing only config1a0->1 for both queues. Existing paired commands, native work records, NOP baseline, aliases and provisional context fields are retained. Expanded analyzer decodes installed firmware rows and the add-kicks counter alongside cursors, crash header, target and completion bytes.

Other hypotheses remain explicit: initial NOPtimestamp0 waits on previous0; baseline-counter correctness is unqualified. Config52=0 separately skips owner-context association; the proposed context seed and actual translation linkage remain unproven. These are subsequent blockers to distinguish after obtaining real queue-install evidence. No direct additional host SGX register writes introduced.

After a normal reboot:

```
sudo -n python experiments/t6040-gpu/run-root-envelope.py out/owned-queue-bind/live-candidate --graph
sudo -n python experiments/t6040-gpu/run-root-envelope.py out/owned-queue-bind/live-candidate --graph --run
python experiments/t6040-gpu/analyze-owned-work.py out/owned-queue-bind/live-candidate/asc-graph-init out/owned-queue-bind/live-candidate/asc-graph-init/boot-<boot-id> out/owned-queue-bind/result-<boot-id>
```

Do not force unload or retry warm INIT. No kernel/default-entry change required. Exact captures in `out/owned-work-publication/live-candidate/asc-graph-init/boot-7f61235c-5ff7-41ad-8e57-cb2b5cdfcce0`; structured decoded result and hashes beside this document. Private implementation-derived research; no clean-room claim.
