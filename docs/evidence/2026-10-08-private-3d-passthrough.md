# Client common render record to native 3D command

Private-derived AGX353.14 / Apple25G83; offline only.
Complete `copy3DCommonPassthroughData` at `89ebbe4..89ebe34` copies a client
`AGX3DCommandCommonRec` into the descriptor. Its caller in `processRenderSetup`
passes the record at a parent source pointer +`2d0` (inspected, not full caller
execution). This establishes a concrete upstream source for many formerly
anonymous register/state fields; it does not identify their hardware semantics.

The independent table is in `private_3d_passthrough.py` and adjacent JSON.
Highlights: common `0..7f` copies contiguously to descriptor `4e8..567`;
common `80..af` goes to descriptor `5e8..617`; many later words are permuted
into descriptor `658..7f8`. Eight flag bytes contribute only their low bit.
The function also fills metadata at `888`, `ad0`, `ad8`, `ae0..b0f`,
`b28..b43` and `410`. Unwritten descriptor bytes remain intact.

1024 cases execute the complete native copier followed by the native ordinary
command body-copy slice `895b604..895b8f8`. Independent models compare full
descriptor, command, source and channel buffers, including the channel counter.
These are separate native calls rather than a complete processRenderSetup or
submit invocation. Inputs are synthetic numeric records, not valid shader or
pipeline state.

The second checker feeds this native copier into the complete common G16 3D
register generator and its SPM/append/encoder helpers. All 128 composed cases
return; 384 helper outputs and 128 descriptor metadata patches match independent
models. Phase-zero's full recipe remains native observed output, not an
independent model. Resource map services remain synthetic and fixtures do not
prove valid draw inputs, live allocation, firmware completion or pixels.

```sh
python experiments/t6040-gpu/audit-private-3d-passthrough.py \
  /boot/GPUC003/private-apple/com.apple.AGXG16X \
  docs/evidence/2026-10-08-private-3d-passthrough.json
python experiments/t6040-gpu/audit-private-3d-input-generator.py \
  /boot/GPUC003/private-apple/com.apple.AGXG16X \
  docs/evidence/2026-10-08-private-3d-input-generator.json
```
