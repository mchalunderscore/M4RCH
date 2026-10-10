The runtime TA-context byte **20→15 at context offset `+4` is a firmware-derived scheduler weight**, causally expected from the intended native subpriority change `0→1`. It does not identify a new context or explain the missing render completion.

The changed byte’s normalized recipe/backing offset is `0xc0204`. Its actual offset in the complete `owned-after.bin` is `0x280204`, owned page 160 plus `0x204`; firmware alias is `0xfffffc2000b18204`. Both selected recipes begin with byte `+4=0`.

| Capture | TA/3D config subpriority | Context weight | Normalized weight | Quantum | Separate selector `+0x33` |
|---|---:|---:|---:|---:|---:|
| eff8 v14 | 0/0 | 20 | 200 | 24,000 | 0 |
| d834 v15 | 1/1 | 15 | 200 | 24,000 | 0 |

Matched firmware loads the context pointer from config `+0x4a` at TEXT `0x19b88`, loads subpriority `+0x5e` at `0x19b8c`, and preserves it at `sp+0x28`. At `0x19e10..0x19e1c`, it indexes TEXT table `0x5ab78 = [20,15,4,1,0]`; at `0x1a300`, it stores the selected byte to context `+4`. Every selected instruction and the table match both actual captured TEXT images. Group/role arithmetic consumes the weight to derive context `+6` and quantum `+0xa`.

The hardware selector is a separate byte at `+0x33`, read at `0x1090c` and written to SGX selector `+0x103a0` at `0x10920`. It remains zero in both captures. This static consumer identifies its role; retained bytes do not establish the current firmware PC or hardware completion.

Matched Apple AGX serialization at `0xfffffe000895be40..0xfffffe000895bf04` publishes the owner’s scheduler pointer as config `+0x4a`, virtual slot `+0x1f0` as subpriority `+0x5e`, and slot `+0x1f8` as PID `+0x5a`. Eight actual Mach-O vtable entries resolve to `AGXChannel::getSubPriority` at `0xfffffe000897de70` or `getPid` at `0xfffffe000897de60`; their mapped-state fields are `+0x40` and `+0x48`. The native scheduler initializer clears 56 bytes before assigning its seed fields, leaving byte `+4=0`.

Selected Gravity `g16_queue.rs::context()` supplies the same 64-byte recipe seed, including `+4=0`, `+0x26=2` and `+0x33=ff`; `g16.rs` publishes it as `BOOT_CONTEXT`. This comparison closes the changed-byte classification. Full G16S scene layout and VM association remain unqualified. The byte’s native C field name has not been recovered; “scheduler weight” is inferred from its exact machine-code producer and consumers. No arbitrary context, active-ID or mask write follows.

Private evidence SHA256: `2d5cbc06c469590b2c8099b6ee2e3672cb890b75e7124b556a60baccb93aee2f`. Matched AGX SHA256: `3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e`. The JSON companion records capture/source pins and bounded range hashes. Private instruction bytes and disassembly remain outside Git. This analysis performed no hardware or candidate changes.
