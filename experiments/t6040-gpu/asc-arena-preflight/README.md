# Expanded initialization arena preflight

This exercises native allocation, shadow walking, firmware-table installation,
cache publication and teardown for 18 candidate backing pages. The expanded
`plan-init-graph.py` requires 17 pages for known minimum extents, including two
for status_b. One extra marker page reserves test capacity for the root+c0
target whose extent is unknown; it is not a complete-size claim. Two additional
owned pages provide the shadow L1 and leaf table (20 x 16 KiB backing in the completed run;21 pages if rebuilt).
The builder generates arena-contract.h and records the page count and source
hashes in its receipt. The firmware-populated root2 descriptor is
preserved; only its verified-empty child slot is installed. Each owned page's
physical address must fit42-bit OAS. Every generated leaf entry is checked.

The pages contain markers and a disabled-allocation root header, not complete
initialization objects. **No root address is sent to firmware.** START32/33 is
followed by bounded observation, AP QUIESCED and IOP SLEEP acknowledgments,
ASC stop readback and empty receive FIFO. Only verified retirement permits
normal unload. Unload removes the child entry, invalidates every generated VA,
frees all owned pages and releases GFX power. Failure retains the probe.

Firmware reads of these pages have not been tested. Successful retirement here
cannot authorize freeing a graph after it has been published/used by firmware.

Reproduce with the matching isolated GPU-contract kernel:

```sh
python experiments/t6040-gpu/build-root-envelope.py out/gpu-gravity-contract
sudo python experiments/t6040-gpu/run-root-envelope.py out/gpu-gravity-contract --arena --run
```

The runner validates fresh metadata and firmware, records the selected build,
and unloads only after retirement logs and zero module refcount agree. The
expanded18-page run passed on boot0ce64a9c-cdcd-4030-b5a8-684d085ba0b7. The
post-unload snapshots confirm zero borrowed L2 and no references to any of the
20 owned pages in the captured table reservations. See
`docs/evidence/2026-10-07-gravity-gpu-expanded-arena-result.json`.

The original attempt receipt kept its initial mapping flag false; the matching
page-count flag and logs confirm installation. The summary documents the
inconsistency and the runner now sets that flag correctly. Normal shutdown
leaves ASC sleeping; another firmware experiment needs a cold reboot, even
though resources are unpinned. This experiment need not be repeated solely
because the firmware is asleep.
