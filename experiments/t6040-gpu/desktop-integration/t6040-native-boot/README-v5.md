# Native T6040 shared bundle component v5

This distinct stage adds the native 25G83 G16X shared allocation and bounded
MainConfig producer to the actual Gravity driver. The frozen v3/v4 components
and the v19/v20/v21 execution candidates remain unchanged.

The selected native constructor produces 23 children, aligned to 64 bytes:
hardware occupies 0x2718 bytes at offset zero, power occupies 0x6578 bytes at
0x5240, MainConfig occupies 0x4c0 bytes at 0x1e100, and the final child ends at
0x225c0. The backing allocation is 0x24000 bytes under the explicit 16 KiB profile
page fixture. Native BRN child 7 has size zero and aliases header child 8 at
0xc040; it receives no separate page or donor fill.

`Platform::native_bundle_component` zeroes the native backing allocation, writes
the existing bounded hardware component within child 0, and calls the native
MainConfig writer. That writer supplies nine native child pointers and two
literal zero stores, preserving all other bytes. The actual bundle method calls
this helper and rejects a full bundle while `BUNDLE_COMPLETE` is false.

The actual Bootstrap selects MainConfig's native address at root+0x18 and the
native backing extent for its FirmwareSpace allocation. Its donor inline
timestamp write at bundle+0x28 is now donor-only, because native child 0 is the
hardware object. Native header contents and timestamp ownership remain unresolved.

Pure Rust qualification compiles the actual component, MainConfig/RootPointers
serializer and Platform bundle/Region C methods with an input/allocation adapter.
Expected child geometry and all compared output bytes derive independently from
the frozen numeric native report. The tests cover zero BRN aliasing, alignment,
overflow and short buffers, preserved unknown bytes and allocation padding,
actual native and donor MainConfig selection, and full-object rejection. Donor
power and hardware methods in the adapter panic if the native branch reaches them.

Stage and qualification run once in a fresh destination:

```sh
python3 experiments/t6040-gpu/desktop-integration/t6040-native-boot/stage_v5.py out/gpu-gravity-normal-boot-v5
python3 experiments/t6040-gpu/desktop-integration/t6040-native-boot/qualify_v5.py out/gpu-gravity-normal-boot-v5 out/gpu-gravity-normal-boot-v5/qualification-v1
```

The root agent owns the subsequent single module build with `build_module_v5.py`.
It uses the existing kernel, persists actual make status before postchecks, and
does not count generated `.mod.c` files as immutable input. No kernel rebuild,
module installation/load or hardware action is part of this stage.

Native raw allocation flags are 0x20900000007; their translation to Linux PTE
permissions remains unqualified. Full hardware, power, channels, callbacks,
Root/Region A/status/Region C contents, header/timestamp ownership and publication
lifetime still require native bindings. Normal startup and full bundle remain
closed. Private binary and instruction bytes are not exported into tracked files.
