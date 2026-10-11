#!/usr/bin/env python3
"""Compose missing ordinary native MainConfig defaults, without hardware."""
def wiring(files):
    key = 'g16_t6040_shared.rs'
    s = files[key]
    needle = '        put64(main,0x200,self.support.base+0x3c100);'
    assert s.count(needle) == 1
    s = s.replace(needle, needle + '''
        // AGXArmFirmware ordinary initialization89cd4bc..508. Accelerator
        // ed20 is G16X inherited virtual10d0,89d7060 returning4. ed94
        // is fresh zero with active-GTP override absent. ecf0 is explicitly
        // zeroed by base configureDevice89679d0, then copied to Main479.
        put32(main,0x300,4);
        put32(main,0x304,0);
        main[0x479..0x489].fill(0);
        main[0x3e0]=0xff;
        main[0x3e1..0x471].fill(0);
        // Optional accelerator f928/f930 service objects absent: native
        //89cd368/404 select zero service pointers; backing is fresh zero.
        main[0x2d8..0x2f8].fill(0);
''')
    files[key] = s
