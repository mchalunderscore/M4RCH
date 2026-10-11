#!/usr/bin/env python3
"""Join Apple slot14 into the normal Gravity mapping producer.

Applied by the combined integration stage; never performs device access.
Slot10 already exists in this producer. Slot14 is the conditional sensor fallback
reached after the captured slot10 fault, with source-bound physical extent.
"""
from pathlib import Path

def wiring(files):
 name='g16_t6040.rs';s=files[name]
 marker='pub(crate) const REGISTER_COUNT: usize = 22;';assert s.count(marker)==1
 s=s.replace(marker,'pub(crate) const REGISTER_COUNT: usize = 23;\nconst SENSOR_FALLBACK_VIRTUAL: u64 = PLATFORM_VIRTUAL + 0x10000;')
 marker='    out[21] = Register { slot: 27, flags: 2, ..Register::default() };'
 assert s.count(marker)==1
 s=s.replace(marker,marker+'''
    // Apple25G83 resource4290: PA500658000, extent10000. Firmware
    // sensor fallback reads+4600/+5600 if active sensors lack validbit31.
    // Read-only firmware permission remains explicit Linux mapping policy.
    out[22] = Register { slot: 14, physical: 0x500658000,
        address: SENSOR_FALLBACK_VIRTUAL, size: 0x10000,
        stride: 0x10000, relative: 0, flags: 0 };
''')
 marker='    // Concatenated IOMemoryDescriptor: four 256 KiB physical regions spaced'
 assert s.count(marker)==1
 s=s.replace(marker,'''    for page in 0..4u64 {
        emit(Page { virtual_address: SENSOR_FALLBACK_VIRTUAL + page * PAGE,
            physical: 0x500658000 + page * PAGE, writable: false })?;
    }
'''+marker)
 files[name]=s
