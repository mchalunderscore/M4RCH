# Native G16 render-storage packing — 2026-10-08

Matched private AGX353.14 / Apple25G83 binary, SHA256 in the JSON. Offline Unicorn execution only; no hardware accesses, Apple executable bytes exported, or rendering claim.

The geometry-sized ordinary render-target region is not the whole allocation. The native update uses a power-of-two rotating storage buffer. This resolves where the three previously traced descriptor addresses originate. A separate GTP-only resource packs eight geometry-derived regions.

## Ordinary render-target ring

Bounded native slices, not the full updateRenderTarget method:

- 8a0affc..8a0b02c: reads object10 as **u32**, adds4095 in32-bit arithmetic, masksfffff000, then stores the result asu64 at10. Entry bytes are padded10 + u6430 + u64260. Required nominal capacity is **16 times entry bytes**. Deliberate wrap cases are characterized; they are not valid render-job inputs.
- 8a0b09c..8a0b0e0: capacity270 grows by doubling from1<<supplied OS page shift until it covers the required bytes. Allocation bytes268 equal capacity270, plus capacity/16 when byte2c0 bit0 is set. Shifts12/14 are supplied fixtures; the actual OS provider is not executed.
- 8a0b294..8a0b2d8: for cursor C, capacity P, padded main bytes M, adjacent bytes N=object30 and E=object260, store offsets2a8=C&(P-1),2b0=(C+M)&(P-1),2b8=(C+M+N)&(P-1). Cursor2a0 advances to C+M+N+E without wrapping. The selected0x58-byte record receives M,N,E in its first24bytes; all remaining record bytes are preserved.

These offsets feed the existing qualified 3D descriptor loader:8a0/8a8/8b0 receive mapped resource base plus2a8/2b0/2b8. Do not replace each address with a separately invented allocation.

Example:64x64, one layer,32x32 utiles gives geometry10=1280, padded main4096, object30=0. If geometry260=0, nominal required ring65536. On supplied shift14, capacity65536 and allocation65536 or69632 depending on byte2c0. With geometry260=512, required73728, capacity131072, allocation131072 or139264. The byte2c0 control and geometry260 depend on native accelerator configuration; neither should be chosen just to minimize memory. Whole resource creation, mapping, ring record/event lifecycle, cursor selection and wait branches remain unqualified here.

## Separate GTP-only packing

Complete updateGtpOnlyBuffers8a0abec..8a0ae74 executes with whole source-object byte comparisons. Sizes S[0..7] are u64 fields140..178. Start offsets O[0]=0; O[i+1]=align(O[i]+S[i], alignment188+8*i) fori0..6. Zero alignment preserves the sum. Tested nonzero alignments are powers of two. Total=O[7]+S[7]. Outputs:1d0 total;1d8..210 eight sizes;218..250 eight offsets. Resource1c0 is distinct from ordinary resource130.

1024 complete reuse cases verify sufficient existing capacity1c8, no external calls, and return resource18. Another512 complete cases cover409 successful and103 failed supplied allocations, with old-resource release paths and optional priority-service calls. On growth, clear1c0/1c8, request total bytes, and on success store new resource and capacity then publish packed fields. On allocation failure return0 and leave derived output fields untouched;1c0/1c8 remain cleared.

Allocation first five argument registers are checked: accelerator120, shared128, total bytes, option3 or1000000003 selected by accelerator6d0 bit47, and range5 or1 respectively. The trailing boolean argument is not explicitly initialized in this function and is **not qualified** by these tests. Supplied retain/release/priority services are checked at their native call sites; their real implementations and backing-memory initialization are not executed. Successful cases return resource18. Priority update uses resource28->78 and object258.

## Coverage and next step

4608 cases total:1024 full reuse,512 full allocation branches, and1024 each for ring sizing, capacity growth and final offset publication. Exact function/range hashes and example inputs are in the JSON. All object bytes compare, including untouched fields; final ring record bytes compare too.

Next qualify ordinary ring allocation options and fresh-record/event setup, then construct a single-flight64x64 storage candidate using actual accelerator/topology inputs. Parameter-management initialization, firmware event/completion backing, queue initialization and native TA/3D relocation remain. No GPU translation, shader execution or pixels are established by this audit.
