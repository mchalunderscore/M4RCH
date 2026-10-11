# Offline native descriptor Fender cycle (v21)

This separate candidate remains **unselected pending the v20 hardware outcome**.
It inherits the v20 draw, capture and retained native NMI/Fender disable cycle.
The actual owner upload changes exactly19 hardware descriptor bytes: flags2 in
slots3/22/39/41 and native zero geometry plus flags2 in slot27. Slot3 still lacks
native MCC geometry. The unused donor slot27 leaf stays retained; mappings,
Linux PTE permissions,174 owned pages, shaders and the four-byte work recipe
stay unchanged. Strict physical OFF and management rejoin checks stay unchanged.

The source preparer checks the frozen v20 arena equals the proposal's frozen
v19 arena and binds the qualified native v3 producer/evidence. It projects both
graph-before.bin and the graph-contract.h array copied by the existing owner
upload, then updates hardware object hashes and descriptor metadata. Qualification
compiles the actual C array and compares every output byte. Finalization also
checks the actual owner ELF graph_bytes symbol. The focused host
check uses one intercepted main flow and composes all frozen qualifications.

```
python3 experiments/t6040-gpu/gfx-native-descriptor-fender-cycle/prepare-descriptor-owner.py --source out/gfx-native-fender-off-cycle/prepared-owner-v1 --destination out/gfx-native-descriptor-fender-cycle/prepared-owner-v1
python3 experiments/t6040-gpu/gfx-native-descriptor-fender-cycle/qualify-descriptors.py --source out/gfx-native-descriptor-fender-cycle/prepared-owner-v1 --output out/gfx-native-descriptor-fender-cycle/descriptor-qualification-v1.json
python3 experiments/t6040-gpu/gfx-native-descriptor-fender-cycle/test-host.py --source out/gfx-native-descriptor-fender-cycle/prepared-owner-v1 --descriptor-qualification out/gfx-native-descriptor-fender-cycle/descriptor-qualification-v1.json --output out/gfx-native-descriptor-fender-cycle/host-qualification-v2.json
```

Root owns module build and finalization. Finalizer CLI:

```
python3 experiments/t6040-gpu/gfx-native-descriptor-fender-cycle/finalize-cold-render.py out/gfx-native-descriptor-fender-cycle/candidate --descriptor-qualification out/gfx-native-descriptor-fender-cycle/descriptor-qualification-v1.json --host-qualification out/gfx-native-descriptor-fender-cycle/host-qualification-v2.json
```

Offline qualification establishes no pixels, physical OFF or DMA retirement.
