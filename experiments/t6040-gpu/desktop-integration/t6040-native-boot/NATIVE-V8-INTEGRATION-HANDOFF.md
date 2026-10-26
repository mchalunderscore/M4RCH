# Native v8 power integration source stage

`stage_v8.py` derives all 75 source files from the frozen, actually compiled v7 source receipt and replaces only the complete power component and three integration files. V7 source/build files are unchanged. The final source stage is `out/gpu-gravity-normal-boot-v8`. The complete power component has independently qualified whole-output agreement for both identity16 and grouped11 performance maps. `qualify_v8.py` composes that proof and the unchanged v7 joined queue proof without rerunning those tests, verifies all immutable inputs and exactly four edited source files, and checks early gating, single map snapshot, and publication order. That qualification passed. `build_module_v8.py` then actually compiled and linked all 75 source files against the existing reset-kernel tree: make exit 0, immutable input changes zero, module 444784 bytes, SHA256 ddcee978dea336a08ac42a0b3bf5b5773185c15e1920843ba19a6b60f3e44c6e. Actual make status, log, and closure are saved under the final stage. Prior draft-2 syntax inspection also passed all four files with rustfmt stdout-only.

The source composes the lifecycle, hardware, Region C, and separate AONPTD writers. It supplies the original raw ADT aliases including perf-states-sram, cs-perf-states, and afr-perf-states. It checks both POWER_COMPLETE and BUNDLE_COMPLETE before mapping or reading hardware. The qualified power gate is true; the full bundle gate remains false, so no hardware access is enabled. Only a future authorized cold boot with those gates qualified reads the two eight-word SGX performance-map banks, once, after validating stopped ASC state and GPU identity and before startup register writes. Actual enabled masks must contain 16 cores in two clusters to accept the explicit Linux 20 W and raw monotonic 24 MHz policy.

The native child0+28 timestamp binding now uses existing TIMESTAMP_BASE through the source-proven selected identity conversion at 89aa3dc..404 / 89c8ff8. The generic donor path retains its existing timestamp write. Existing runtime reserve_timestamp/map_timestamp owns and maps only allocated subranges of that aperture; the base itself is an address window, not 64 MiB of fabricated backing.

## Ownership and publication

- Support child26 VA 0xfffffc20000f3180 is within the retained support allocation at 0xfffffc2000030000, backing 0xc4000. Its logical offset is 0xc3180.
- QoS VA 0xfffffc200012c000 has its own existing allocated 16 KiB FirmwareSpace page, initialized by the qualified persistent QoS writer. The lifecycle hardware producer receives this identical VA for child0+26b8.
- AONPTD VA 0xfffffc2000110000 has its own existing allocated 16 KiB FirmwareSpace page. V8 writes the complete AON logical producer there before graph publication. The lifecycle producer receives this same VA for power+6318.
- Region C has an existing allocated retained page, and V8 publishes the complete power writer's result rather than the legacy donor Platform::region_c path.
- Both independent pages are allocated before Bootstrap::publish sends the initialization graph. There is no missing page allocation for QoS/AON; they do not alias shared support or each other.
- Preserved power provider slots 6530..6538 and 2888..28b8 are captured from the fresh owned zeroed power child before the lifecycle writer. A previous consumed boot is never sampled or copied.

## Remaining integration limits

Independent complete power output agreement and the real combined module build are complete. The full bundle gate remains closed. The loader contract checks original firmware identifier, firmware private-VM geometry, and aligned nonoverlapping ttbs/pagetables/l2/handoff/firmware reservations; the firmware UAT still attaches the loader-owned pagetables root. This source stage does not produce or install that loader reservation contract or enable a DT GPU node.

Bootstrap retains every native session object on Drop when the constructed session may have firmware access. Before construction completes, FirmwareSpace::Drop removes mappings; it is only valid before graph publication or after firmware stop. V7 builds all mappings before sending the root through Bootstrap::publish. Any future reordering that exposes root/queue addresses before the Bootstrap owner exists must preserve that lifetime requirement. No teardown qualification is implied by this integration.

Only the module was built offline; the existing kernel was not rebuilt. Nothing was installed, loaded, unloaded, or sampled. No hardware was accessed. This is not a READY triangle candidate.
