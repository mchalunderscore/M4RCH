# Linux-owned native-derived render storage passed — 2026-10-08

The authored Apple9 shader,64x64 target and draw-state preparation now optionally consumes the hash-checked native fresh-target storage profile. It rechecks ring capacity/entry/offset fields against the source fixture, recomputes separate GTP packing, checks target dimensions, alignment and address collisions, and appends allocation-only zero backing for the ring and GTP.

Runtime allocation-only gate1:31 render/storage data pages,6 table pages,507904 payload bytes copied/compared and all31 leaf walks checked. Nine new data pages:8x16KiB ring at1000040000..100005c000 and one16KiB backing page for13824 logical GTP bytes at1000060000. These reuse the existing device-root1 L1/L2 table with draw-state1000000000. Existing shader-root16 and target-root2 regions unchanged.149 total owned allocations;100 device leaves;206 firmware-shadow leaves. Normal unload released owned backing; module absent. Firmware root/context not published, no GPU job/lookup/execution/pixels.

W=1 module build passed on7.1.13-m4rch-gpu-contract, boot8d5519d3-c1db-41a7-bb94-7c68e7ac0d10. Exact build/module, preparation, fixture profile and dmesg retained in the private return bundle. Default preparation without --storage-profile retains22 data pages and its payload is byte-identical to previous authored candidate backing.

This qualifies real Linux allocation/readback/shadow mapping for derived storage sizes, not native data initialization. The new regions are zero placeholders: PM/GTP required contents, event setup, true topology/configuration and final TA/3D relocation remain. Leaf flags stay candidatee0000000000c0b, not hardware-qualified execution/cache permissions. No reboot required by this trial.
