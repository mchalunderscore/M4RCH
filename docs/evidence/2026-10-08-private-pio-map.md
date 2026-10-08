# Native single-region CPU PIO mapping

Private-derived AGX353.14 / Apple25G83, offline only. Binary SHA and native
slice SHA are recorded in the adjacent JSON; no private executable bytes are exported.

Complete `createCPUPIOMapping` at `8977fd8..8978284` executes in Unicorn with
synthetic memory-descriptor factory, map, address and release providers. It uses
descriptor base `998`, stride `438`, flags at +0, segment count at +4,
physical start at +8 and extent at +208. For a single segment it calls the
factory with page-aligned physical start, rounded covering length and
`(flags & 2) | 1`; passes the caller's options to map; caches the returned
virtual address at `f780 + region*8` and map object at `f5d8 + region*8`;
then releases the temporary descriptor.

1152 successful cases cover six region indices, three CPU page sizes, both
flag states and randomized physical inputs, lengths, options and virtual
addresses. The entire accelerator fixture is compared, including unchanged bytes.
Another 1024 cases cover four outcomes: zero segments, factory failure,
map failure and a mapping whose address provider returns zero. The first three
return zero and preserve existing caches. The last caches zero/address object
and returns one; this characterizes the native contract, not a hardware bug.
PAC is bypassed; multi-segment mapping and real mapping provider behavior are untested.

Region 45 has descriptor `c770` and virtual cache `f8e8`, the exact Fender
pointer consumed by the previously audited gating methods. Consequently
`c774` is the descriptor's segment count, refining the earlier description
as a mode selector. A count of one selects the direct mapped path. `c980`
is the descriptor's relative logical offset. The generic configuration routine
names this region “Probe-time Fender mapping”. Physical inputs in this checker
are fixtures, not measurements of the running hardware.

Run:

```sh
python experiments/t6040-gpu/audit-private-pio-map.py \
  /boot/GPUC003/private-apple/com.apple.AGXG16X \
  docs/evidence/2026-10-08-private-pio-map.json
```
