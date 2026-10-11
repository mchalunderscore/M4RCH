#!/usr/bin/env python3
"""Connect the cold read-only factory inputs to the joined power writer."""
from pathlib import Path
KIT = Path(__file__).resolve().parent


def wiring(files):
    module = 'g16_t6040_factory_leakage_v10'
    files[module + '.rs'] = (KIT / (module + '.rs')).read_text()
    s = files['asahi_m4.rs']
    marker = 'mod g16_vm;'
    assert s.count(marker) == 1
    files['asahi_m4.rs'] = s.replace(marker, '#[allow(dead_code)] mod ' + module + ';\n' + marker)
    s = files['g16_power.rs']
    marker = '        policy: &crate::g16_t6040_power::LinuxBootPolicy,\n'
    assert s.count(marker) == 1
    s = s.replace(marker, marker + '        factory: &crate::g16_t6040_factory_leakage_v10::FactoryLeakage,\n')
    marker = '''        power.write_hardware_component(&mut out[hardware.offset..hardware.offset + hardware.bytes],'''
    assert s.count(marker) == 1
    s = s.replace(marker, '''        factory.write_power(&mut out[child.offset..child.offset + child.bytes]).ok_or(EINVAL)?;
''' + marker)
    files['g16_power.rs'] = s
    s = files['g16.rs']
    marker = '            (bundle, region_c, native_aonptd) = platform.native_boot_components(&maps, &policy)?;'
    assert s.count(marker) == 1
    s = s.replace(marker, '''            // Match the successful native factory provider, not the optional
            // mapping-failure zero fallback. One read-only cold snapshot while
            // this session owns PM, before the first ASC start/publication.
            let mut fuse_words = [0u32; 5];
            // SAFETY: Fixed-size output lives through the read-only helper.
            kernel::error::to_result(unsafe {
                kernel::bindings::native_gpu_factory_leakage_snapshot(fuse_words.as_mut_ptr())
            })?;
            let factory = crate::g16_t6040_factory_leakage_v10::FactoryLeakage::from_words(&fuse_words);
            (bundle, region_c, native_aonptd) = platform.native_boot_components(&maps, &policy, &factory)?;''')
    files['g16.rs'] = s


def kernel_wiring(files):
    marker = '#include "device.c"'
    assert files['rust/helpers/helpers.c'].count(marker) == 1
    files['rust/helpers/helpers.c'] = files['rust/helpers/helpers.c'].replace(
        marker, marker + '\n#include "native_gpu_factory.c"')
    files['rust/helpers/native_gpu_factory.c'] = (KIT / 'native_factory_helpers_v10.c').read_text()
