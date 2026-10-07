# Expanded initialization arena preflight

This exercises native allocation, shadow walking, firmware-table installation,
cache publication and teardown for 18 candidate backing pages. The expanded
`plan-init-graph.py` requires 17 pages for known minimum extents, including two
for status_b. One extra marker page reserves test capacity for the root+c0
target whose extent is unknown; it is not a complete-size claim. Two additional
owned pages provide the shadow L1 and leaf table (20 x 16 KiB backing total).
The builder generates arena-contract.h and records the page count and source
hashes in its receipt. The firmware-populated root2 descriptor is
preserved; only its verified-empty child slot is installed. Each owned page's
physical address must fit 42-bit OAS. All 18 leaf entries are checked.

The pages contain markers and a disabled-allocation root header, not complete
initialization objects. **No root address is sent to firmware.** START32/33 is
followed by bounded observation, AP QUIESCED and IOP SLEEP acknowledgments,
ASC stop readback and empty receive FIFO. Only verified retirement permits
normal unload. Unload removes the child entry, invalidates all 18 VAs,
frees the 20 pages and releases GFX power. Failure retains the probe.

Firmware reads of these pages have not been tested. Successful retirement here
cannot authorize freeing a graph after it has been published/used by firmware.

Reproduce with the matching isolated GPU-contract kernel:

```sh
python experiments/t6040-gpu/build-root-envelope.py out/gpu-gravity-contract
sudo python experiments/t6040-gpu/run-root-envelope.py out/gpu-gravity-contract --arena --run
```

The runner validates fresh metadata and firmware, records the selected build,
and unloads only after retirement logs and zero module refcount agree. The
earlier 13-page native run used the same checks in a capture harness. Neither
the shared runner nor the expanded 18-page variant has been exercised on a
fresh boot yet. The updated runner also captures table/L2 snapshots after unload
and checks all 20 owned physical pages for remaining references. Read-only
post-unload table snapshots from the first run show the
reserved L2 page restored to zero and no references to any owned page in the
captured table/L2 reservations. Normal shutdown leaves ASC sleeping; another
firmware experiment needs a cold reboot, even though resources are unpinned.
