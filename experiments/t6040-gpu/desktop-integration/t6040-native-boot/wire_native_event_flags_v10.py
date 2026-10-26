#!/usr/bin/env python3
"""Compose native ordinary event flags into the retained actual caller."""
from pathlib import Path
KIT=Path(__file__).resolve().parent

def wiring(files):
    files['g16_t6040_event_flags_v10.rs']=(KIT/'g16_t6040_event_flags_v10.rs').read_text()
    s=files['asahi_m4.rs'];anchor='mod g16_vm;'
    if 'mod g16_t6040_event_flags_v10;' not in s:
        assert s.count(anchor)==1
        s=s.replace(anchor,'#[allow(dead_code)] mod g16_t6040_event_flags_v10;\n'+anchor)
    files['asahi_m4.rs']=s
    s=files['g16_runtime.rs']
    before='''            // LINUX_NATIVE_MASK_PLACEMENT supplies actual topology masks in
            // the first two mask words; Apple's scheduling policy is unbound.
            masks:[self.topology.core_masks[0],self.topology.core_masks[1],0,0],auxiliary:stage.shared_state_fw};'''
    after='''            // Ordinary AGFIKSMEventFlagMask derives from native RegionC
            // e1c=0, absent optional owner, and PPP policy byte6d7=0.
            masks:crate::g16_t6040_event_flags_v10::ordinary(
                crate::g16_t6040_event_flags_v10::Inputs{firmware_e1c:0,
                    descriptor_optional_owner:false,accelerator_6d7:0}),
            auxiliary:stage.shared_state_fw};'''
    if before in s:
        assert s.count(before)==1;s=s.replace(before,after)
    elif 'crate::g16_t6040_event_flags_v10::ordinary(' not in s:
        raise ValueError('Expected native KSM mask caller not present')
    s=s.replace('''        // LINUX_QOS_RECORD_POLICY currently selects0/16/0; real topology masks
        // come from this device's retained ADT-derived profile.''','''        // QOS comes from the requested ordinary scheduling policy;
        // event flags derive from the serialized native configuration.''')
    files['g16_runtime.rs']=s
