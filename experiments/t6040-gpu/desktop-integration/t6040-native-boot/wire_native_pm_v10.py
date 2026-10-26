#!/usr/bin/env python3
"""Connect native PM session ownership; stage helpers before the whole build."""
from pathlib import Path
KIT = Path(__file__).resolve().parent


def wiring(files):
    module = 'g16_native_pm_v10'
    files[module + '.rs'] = (KIT / (module + '.rs')).read_text()
    s = files['asahi_m4.rs']
    marker = 'mod g16_vm;'
    assert s.count(marker) == 1
    files['asahi_m4.rs'] = s.replace(marker, '#[allow(dead_code)] mod ' + module + ';\n' + marker)
    s = files['g16.rs']
    def replace(before, after):
        nonlocal s
        assert s.count(before) == 1, (before, s.count(before))
        s = s.replace(before, after)
    replace('    _asc: Pin<KBox<Devres<IoMem<0x4000>>>>,',
            '    _asc: Pin<KBox<Devres<IoMem<0x4000>>>>,\n    native_pm_session: Option<crate::g16_native_pm_v10::Session>,')
    marker = '        let asc = KBox::pin_init('
    assert s.count(marker) == 1
    s = s.replace(marker, '''        let mut native_pm_session = if native_t6040 {
            Some(crate::g16_native_pm_v10::Session::acquire(pdev)?)
        } else { None };
''' + marker)
    replace('        asc_guard.relaxed().write32(control | 0x10, 0x44);',
            '''        if let Some(session) = native_pm_session.as_mut() { session.mark_exposed(); }
        asc_guard.relaxed().write32(control | 0x10, 0x44);''')
    marker = '        let notifications = Arc::pin_init(Notifications::new(), GFP_KERNEL)?;'
    assert s.count(marker) == 1
    s = s.replace(marker, '''        if let Some(session) = native_pm_session.as_mut() {
            session.coordinate(true)?;
        }
''' + marker)
    replace('            _asc: asc,', '            _asc: asc,\n            native_pm_session,')
    files['g16.rs'] = s


def kernel_wiring(files):
    marker = '#include "device.c"'
    assert files['rust/helpers/helpers.c'].count(marker) == 1
    files['rust/helpers/helpers.c'] = files['rust/helpers/helpers.c'].replace(
        marker, marker + '\n#include "native_gpu_pm.c"')
    files['rust/helpers/native_gpu_pm.c'] = (KIT / 'native_pm_helpers_v10.c').read_text()
    files['rust/helpers/helpers.c'] = files['rust/helpers/helpers.c'].replace(
        '#include "native_gpu_pm.c"', '#include "native_gpu_pm.c"\n#include "native_gpu_coordinate.c"')
    files['rust/helpers/native_gpu_coordinate.c'] = (KIT / 'native_coordinate_helpers_v10.c').read_text()
    files['rust/helpers/native_gpu_coordinate_core.h'] = (
        KIT.parent.parent / 'gfx-coordinate-native-status/gfx-coordinate-core.h').read_text()
