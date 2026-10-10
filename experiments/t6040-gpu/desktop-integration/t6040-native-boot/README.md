# Native T6040 components in the Gravity backend

This stage adds real T6040 register and voltage producers to the existing
Gravity `asahi_m4` module. `Platform::new(dev, profile)` selects the native
component for chip6040/variantS; `Platform::hwdata()` serializes that component;
the existing `FirmwareSpace` mapping loop consumes its page plan.

The source comes from the matched 25G83/AGX353.14 PIO table, GPUC003 platform
constructor, GPUC004 segmented AFR constructor, and captured J614s performance
tables. The component contains twelve native primary PIO rows, four platform
pages, the four-range AFR mapping, independently decoded core/SRAM voltage
columns for two clusters, and the packed two-cluster core mask. It preserves
SGX-relative firmware addresses. Descriptor flags and page write permission
are separate inputs; permissions preserve the explicit consumer-based
experimental selections from earlier trials.

This is a partial hardware-data component. Its `0x2570` backing is the minimum
extent for fields it writes, not a claimed native object size. Only component
fields are populated. It contains no T8132 boot bundle, main graph, power
controllers, MCC defaults, channel roots, or physical work cursors.
`Platform::bundle()`, `power_data()`, and `region_c()` reject this profile.
The existing normal T6040 execution gate remains false. The only normal
`hwdata()` publication consumer is `bundle()`, whose rejection occurs before
copying the component. A constructor or mapping typecheck does not prove GPU
startup or completion.

Slots3/22/27/39/41 are deliberately absent in this first compiled component.
The native PIO table's slot44 alternate mapping is also not silently converted
to a primary mapping. A native constructor input must replace each missing
resource before normal firmware startup; zero descriptors are not a working
replacement for required resources.

Loader inputs for this new constructor use the existing Gravity OF convention:
`reg` identifies ASC followed by SGX, `apple,m4-core-masks` is a big-endian OF
array of two masks, `apple,sgx-perf-states` and
`apple,sgx-perf-states-sram` retain the raw little-endian ADT pair arrays,
`apple,m4-max-power-mw` supplies a measured board maximum, and
`apple,chip-revision` supplies the revision. These properties have not been
installed into the live device tree.

Reproduce a fresh full module source stage and exercise the actual Rust
component against independent saved numerical inputs:

```sh
python3 experiments/t6040-gpu/desktop-integration/t6040-native-boot/stage.py out/native-t6040-new
python3 experiments/t6040-gpu/desktop-integration/t6040-native-boot/qualify.py out/native-t6040-new out/native-t6040-new-qualification
make -C out/gfx-native-reset-kernel/linux M="$PWD/out/native-t6040-new/build-owner" LLVM=1 W=1 modules
```

These commands do not load the module or access GPU hardware. The kernel build
tree may require the root owner's build authority. Use a new output directory
for a changed stage; do not mutate the compiled source or repeat an unchanged
hardware trial.
