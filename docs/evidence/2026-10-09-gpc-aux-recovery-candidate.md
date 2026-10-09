# Native CS/AFR initialization recovery candidate

Prepared, built and reviewed; no live result yet. This extends the GPC-enabled
trial that stalled before consuming the initial controls on boot
`706d9e50-c897-4479-8587-f19835a40166`.

The candidate restores two independently specified native auxiliary domains:
CS at hardware `1a48` and AFR at `1b90`. Each captured ADT table has eight states,
so its native maximum and cap are 7. Frequencies are 24, 338, 618, 796, 992,
1188, 1380 and 1470 MHz. Core voltages are 590, 590, 625, 665, 715, 775, 860,
900 mV; SRAM voltages are the maximum of the core voltage and the ADT floor of
810 mV. Only the ADT's one voltage column is populated; unused columns and rows
are zero. Both complete blocks total 164 u32 fields.

The helper's entire output matches the actual native ADT parser, domain-cap
method and hardware-table producer executed in RAM. Six native instruction-span
hashes, the domain-name strings and G16X cap vtable target bind the implementation.
Native capability bytes gate the two producer blocks; `has-kf=1` is a board
guard, not a claim that it aliases both capability bits. Populating both native
tables is the explicit next integrated hardware hypothesis.

The main GPU ladder remains capped at its first active 338 MHz group. Auxiliary
cap 7 does not force state 7: firmware takes the minimum of its requested state
and the cap, so startup request 1 remains 1 rather than being clamped to zero.
These CS/AFR blocks are separate from the main GPU profile-B table, which is
still unqualified and disabled.

The same batch makes only physical page `0x288d60000` writable. With the
candidate's hardware `e88=0`, firmware selects descriptor32's base, publishes it
through `190e30 -> 14a1e8`, and stores timestamps at offsets 0 and `40`. The
descriptor flag, generated PTE header, receipt and both loader allowlists now
agree. The other seven pages in descriptor32 retain read-only PTEs.

The retained diagnostic sampler now includes startup failure before the first
control record, as well as recovery phase 2. It records the six fixed native
poll operands already sampled on the preceding boot; it has no arbitrary MMIO
or selector-write interface. Failed sessions still admit only sample/stop.
Work publication requires two complete recovery cycles and fresh controls.

Prepared graph: `out/gpc-aux-recovery/prepared`.
Runnable candidate: `out/gpc-aux-recovery/candidate`.
Module SHA256:
`399e92e2b25fcafd3aa4ca7214bce65e41398310c8772f7c030311a7f6a5cf5e`.

`W=1` build and source/artifact receipts pass. The graph differs from the last
GPC trial by exactly 99 bytes, all within the two auxiliary blocks and the
slot32 descriptor flag. Exactly one MMIO leaf changes permission. The complete
draw backing, shaders, commands and completion rings are byte-identical.
All 174 owned pages and the joined context remain retained. No recovery reuse,
DMA retirement or rendering is established by preparing this candidate.

After a fresh normal reboot, with the old module absent:

```sh
sudo -n python experiments/t6040-gpu/run-root-envelope.py out/gpc-aux-recovery/candidate --graph --run
```

If both cycles succeed, use the same retained instance to verify further idle
recovery and then submit its one immutable triangle. If it fails, inspect the
captured poll operands and use only the typed sample/stop interface. Do not
repeat START/INIT wake attempts or force unload the retained context.
