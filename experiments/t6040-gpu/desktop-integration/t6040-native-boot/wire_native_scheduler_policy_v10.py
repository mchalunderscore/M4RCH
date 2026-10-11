#!/usr/bin/env python3
"""Bind one owned scheduler policy to hardware, queue and event conversion."""
def wiring(files):
    key = 'g16_t6040_event_timeline_v9.rs'
    s = files[key]
    needle = '#[derive(Clone,Copy,Debug,PartialEq)]'
    assert s.count(needle) == 1
    s = s.replace(needle, '''// Explicit Linux allocation policy, shared by hardware261c and every queue.
pub(crate) const CAPACITY: u16 = 256;
''' + needle)
    s = s.replace('convert_timestamp(epoch,event,256,initial)',
                  'convert_timestamp(epoch,event,CAPACITY,initial)')
    files[key] = s
    key = 'g16_runtime.rs'
    s = files[key]
    needle = 'u8::try_from(id).map_err(|_|EINVAL)?,256,timestamp,0,cached_previous)'
    assert s.count(needle) == 1
    s = s.replace(needle, 'u8::try_from(id).map_err(|_|EINVAL)?,crate::g16_t6040_event_timeline_v9::CAPACITY,timestamp,0,cached_previous)')
    s = s.replace("// LINUX_NATIVE_SCHEDULER_EPOCH explicitly uses requested Linux counter\n        // start; Apple's accelerator ee48 initializer is not claimed equal.",
                  '// Hardware2614 and this queue share the requested Linux initial\n        // timestamp, following native accelerator ee48 owner propagation.')
    files[key] = s
    key = 'g16_power.rs'
    s = files[key]
    needle = 'put64(&mut out, hardware.offset + 0x28, crate::g16_fw::TIMESTAMP_BASE);'
    assert s.count(needle) == 1
    s = s.replace(needle, needle + '''
        // Native89aa434..448 copies accelerator ee40/ee48 into child0
        // +261c/+2614. createKSMKickQueues8972714..20 uses the same owners.
        // Linux supplies its allocated capacity and requested initial counter
        // consistently; this does not infer Apple's debug override defaults.
        let initial=*crate::module_parameters::fw_counter_start.value();
        if initial >> 40 != 0 { return Err(EINVAL); }
        put64(&mut out, hardware.offset + 0x2614, initial);
        put32(&mut out, hardware.offset + 0x261c,
            u32::from(crate::g16_t6040_event_timeline_v9::CAPACITY));
''')
    files[key] = s
