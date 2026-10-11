# Native Region C component in Gravity

V4 adds a source-proved Region C allocation and initial component to the actual
native `Platform` producer. The matched driver allocates 0xe58 logical bytes at
child offset zero, rounds the shared allocation to 0x4000 bytes, zeroes its
backing, and publishes its GPU address at root offset 0x20.

The component serializes only native initial literals and two native idle-delay
inputs. Absent ADT properties select 2 ms for GPU idle and 40 ms for Fender idle;
present properties are raw little-endian words. The proposed OF bridge preserves
those bytes as `apple,sgx-gpu-idle-off-delay-ms` and
`apple,sgx-gpu-fender-idle-off-delay-ms`. This bridge is specified but is not
installed into a device tree.

`Platform::native_region_c_component()` allocates and produces the component.
The actual `region_c()` path calls it and retains `ENOTSUPP` while
`REGION_C_COMPLETE` is false. The full native bundle, power, Region C callbacks,
and Linux mapping-policy translation remain incomplete; normal startup stays
disabled. The existing Region C mapping selection is preserved as unqualified.

The offline qualifier exercises the actual component, existing native hardware
and root serializers, and actual `Platform` Region C methods with an input and
allocation adapter. It compares complete allocation-sized output, preserves
unknown bytes/padding, checks little-endian overrides and malformed properties,
and verifies the full-object rejection. It does not publish memory to a GPU.

Create a fresh stage and run the pure Rust qualification once:

```sh
python3 experiments/t6040-gpu/desktop-integration/t6040-native-boot/stage_v4.py out/gpu-gravity-normal-boot-v4
python3 experiments/t6040-gpu/desktop-integration/t6040-native-boot/qualify_v4.py out/gpu-gravity-normal-boot-v4 out/gpu-gravity-normal-boot-v4/qualification-v1
```

The designated root build owner may compile the new module against the existing
kernel with `build_module_v4.py out/gpu-gravity-normal-boot-v4`. Its helper
persists make status before postchecks and performs no install, load, kernel
rebuild, or hardware action. V3 and the execution candidates remain separate.
